import streamlit as st
import pandas as pd
import plotly.express as px
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="Ипотечное страхование недвижимости в Сбере",
    layout="wide",
    initial_sidebar_state="collapsed"
)

@st.cache_data
def load_data():
    df = pd.read_csv('sber_mortgage_insurance_funnel_problems.csv', parse_dates=['date'])
    metrics_df = pd.read_csv('metrics_summary.csv')
    return df, metrics_df

df, metrics_df = load_data()

def safe_float(val):
    try: return float(val)
    except: return val


def find_main_drop_point(df):
    """Находит этап с максимальным отвалом и главную причину"""
    
    # Порядок этапов воронки
    stages_order = ['impression', 'click', 'form_start', 'form_complete', 
                    'price_view', 'payment_start', 'paid']
    
    # Считаем количество пользователей на каждом этапе
    stage_counts = df.groupby('funnel_stage')['user_id'].nunique()
    
    # Считаем конверсию между этапами и отвалы
    drop_analysis = []
    for i in range(len(stages_order) - 1):
        curr_stage = stages_order[i]
        next_stage = stages_order[i + 1]
        
        curr_count = stage_counts.get(curr_stage, 0)
        next_count = stage_counts.get(next_stage, 0)
        
        if curr_count > 0:
            drop_count = curr_count - next_count
            drop_rate = (drop_count / curr_count) * 100
            
            # Находим топ-причину отвала на этом этапе
            stage_drops = df[
                (df['funnel_stage'] == curr_stage) & 
                (df['drop_reason'].notna())
            ]
            
            top_reason = '—'
            reason_count = 0
            if len(stage_drops) > 0:
                reason_counts = stage_drops['drop_reason'].value_counts()
                if len(reason_counts) > 0:
                    top_reason = reason_counts.index[0]
                    reason_count = reason_counts.iloc[0]
            
            drop_analysis.append({
                'from_stage': curr_stage,
                'to_stage': next_stage,
                'drop_count': drop_count,
                'drop_rate': drop_rate,
                'top_reason': top_reason,
                'reason_count': reason_count
            })
    
    # Находим этап с максимальным отвалом
    if drop_analysis:
        main_drop = max(drop_analysis, key=lambda x: x['drop_rate'])
        return main_drop, drop_analysis
    return None, drop_analysis

# Запускаем анализ
main_drop, all_drops = find_main_drop_point(df)

metrics = {row['metric']: safe_float(row['value']) for _, row in metrics_df.iterrows()}

CONV = metrics['Overall conversion rate, %']
CONV_COUNT = int(metrics['Total converted'])
AVG_CHECK = metrics['Average premium (paid only), RUB']
GWP = metrics['Total GWP (Gross Written Premium), RUB']

# Логика рекомендаций (ЕСЛИ → ТО)
def get_recommendations(conv, conv_count, avg_check, gwp, df):
    recs = []
    if conv < 5.0:
        recs.append(('HIGH', f'Конверсия: {conv:.1f}%', 'Критически низкая конверсия воронки', 
                     'Запустить срочный A/B-тест: упрощённая форма + автозаполнение', '+3–5 п.п. к конверсии'))
    elif conv < 7.0:
        recs.append(('MEDIUM', f'Конверсия: {conv:.1f}%', 'Ниже целевого уровня', 
                     'Проанализировать drop_reason + провести юзабилити-тесты', '+1–3 п.п.'))
        
    expected_conv_count = len(df) * 0.085
    if conv_count < expected_conv_count * 0.8:
        recs.append(('HIGH', f'Купившие: {conv_count:,}', 
                     f'Падение на {100 - conv_count/expected_conv_count*100:.0f}% к ожидаемому', 
                     'Проверить сезонность + запустить ретаргетинг в "проседающих" регионах', '+15–25% к покупкам'))
                     
    if avg_check < 17000 or avg_check > 23000:
        dev = (avg_check - 20000) / 20000 * 100
        recs.append(('MEDIUM', f'Средний чек: {avg_check:,.0f} ₽', 
                     f'Отклонение на {dev:+.1f}% от нормы', 
                     'Проверить структуру полисов и долю онлайн-скидок', 'Стабилизация ±10%'))
                     
    expected_gwp = len(df) * 0.085 * 20000
    if gwp < expected_gwp * 0.85:
        recs.append(('HIGH', f'Сборы (GWP): {gwp:,.0f} ₽', 
                     f'Ниже плана на {100 - gwp/expected_gwp*100:.0f}%', 
                     'Комплекс мер: ↑конверсия + ↑чек + ↑трафик', '+10–20% к сборам'))
                     
    if not recs:
        recs.append(('OK', 'Все метрики', 'в норме', 
                     'Продолжать мониторинг и тестировать гипотезы роста', 'Стабильный рост'))
    return recs

recs = get_recommendations(CONV, CONV_COUNT, AVG_CHECK, GWP, df)


st.title("Ипотечное страхование недвижимости в Сбере")
st.caption("Аналитика воронки продаж | 4 ключевые метрики | Система принятия решений")

# 4 метрики (адаптивные карточки)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Конверсия", f"{CONV:.1f}%")
c2.metric("Купившие", f"{CONV_COUNT:,}")
c3.metric("Средний чек", f"{AVG_CHECK:,.0f} ₽")
c4.metric("Сборы (GWP)", f"{GWP:,.0f} ₽")

# if main_drop:
#     st.subheader("Главная проблема воронки")
    
#     # Красивая карточка с проблемой
#     col1, col2 = st.columns([3, 2])
    
#     with col1:
#         # Этап отвала
#         stage_labels = {
#             'impression': 'Просмотр',
#             'click': 'Клик',
#             'form_start': 'Начало формы',
#             'form_complete': 'Завершение формы',
#             'price_view': 'Просмотр цены',
#             'payment_start': 'Начало оплаты',
#             'paid': 'Покупка'
#         }
        
#         st.metric(
#             label="Максимальный отвал",
#             value=f"{main_drop['drop_rate']:.1f}%",
#             delta=f"-{main_drop['drop_count']:,.0f} пользователей"
#         )
        
#         st.markdown(f"**Этап:** {stage_labels.get(main_drop['from_stage'], main_drop['from_stage'])}")
#         st.markdown(f"**Переход:** → {stage_labels.get(main_drop['to_stage'], main_drop['to_stage'])}")
    
#     with col2:
#         # Кастомная метрика с тёмным фоном для длинного текста
#         st.markdown(f"""
#         <div style="
#             background-color: #262730;
#             border: 1px solid #3d3d4a;
#             border-radius: 10px;
#             padding: 16px;
#             margin-bottom: 8px;
#         ">
#             <p style="
#                 color: #9da0a6;
#                 font-size: 14px;
#                 margin: 0 0 4px 0;
#                 font-family: 'Source Sans Pro', sans-serif;
#             ">Главная причина</p>
#             <p style="
#                 color: #fafafa;
#                 font-size: 22px;
#                 font-weight: 600;
#                 margin: 0;
#                 font-family: 'Source Sans Pro', sans-serif;
#                 word-wrap: break-word;
#                 overflow-wrap: break-word;
#                 line-height: 1.3;
#             ">{main_drop['top_reason']}</p>
#         </div>
#         """, unsafe_allow_html=True)
        
#         st.caption(f"Указали {main_drop['reason_count']} пользователей")
        
#         # Краткая рекомендация
#         recommendations = {
#             'Не заинтересовал заголовок': 'Протестировать варианты заголовков и ценностное предложение',
#             'Ушёл по сравнению на banki.ru / sravni.ru': 'Подсветить преимущества Сбера: скорость, интеграция',
#             'Сложная форма': 'Упростить форму: автозаполнение, меньше полей',
#             'Передумал страховать': 'Настроить ретаргетинг с персональным оффером',
#             'Дорого': 'Показать цену «в месяц», добавить рассрочку',
#             'Нашёл дешевле у конкурента': 'Сравнительная таблица с конкурентами',
#             'Не понял, что входит': 'Добавить чеклист покрытия и тултипы',
#             'Долго грузилось': '⚡ Оптимизировать скорость загрузки страниц',
#             'Техническая ошибка': 'Срочно проверить логи и исправить баги',
#             'Проблема с картой': 'Добавить больше способов оплаты',
#             'Передумал в последний момент': 'Напоминание в СберБанк Онлайн через 1 час',
#             'Технический сбой': 'Мониторинг ошибок + fallback-сценарии',
#             '—': 'Настроить детальное логирование причин отвалов'
#         }
        
#         rec_text = recommendations.get(main_drop['top_reason'], 'Провести юзабилити-тесты')
#         st.info(f"**Рекомендация:** {rec_text}")

if main_drop:
    st.subheader("Главная проблема воронки")
    
    # Красивая карточка с проблемой
    col1, col2 = st.columns([3, 2])
    
    with col1:
        # Этап отвала
        stage_labels = {
            'impression': 'Просмотр',
            'click': 'Клик',
            'form_start': 'Начало формы',
            'form_complete': 'Завершение формы',
            'price_view': 'Просмотр цены',
            'payment_start': 'Начало оплаты',
            'paid': 'Покупка'
        }
        
        st.metric(
            label="Максимальный отвал",
            value=f"{main_drop['drop_rate']:.1f}%",
            delta=f"-{main_drop['drop_count']:,.0f} пользователей"
        )
        
        st.markdown(f"**Этап:** {stage_labels.get(main_drop['from_stage'], main_drop['from_stage'])}")
        st.markdown(f"**Переход:** → {stage_labels.get(main_drop['to_stage'], main_drop['to_stage'])}")
    
    with col2:
        st.markdown("###### Главная причина")
        st.markdown(
            f"<span style='font-size: clamp(1rem, 3.5vw, 1.5rem); "
            f"font-weight: 600; "
            f"display: block; "
            f"word-wrap: break-word; "
            f"overflow-wrap: break-word; "
            f"line-height: 1.3;'>"
            f"{main_drop['top_reason']}"
            f"</span>",
            unsafe_allow_html=True
        )
        
        st.caption(f"Указали {main_drop['reason_count']} пользователей")
        
        recommendations = {
            'Не заинтересовал заголовок': 'Протестировать варианты заголовков и ценностное предложение',
            'Ушёл по сравнению на banki.ru / sravni.ru': 'Подсветить преимущества Сбера: скорость, интеграция',
            'Сложная форма': 'Упростить форму: автозаполнение, меньше полей',
            'Передумал страховать': 'Настроить ретаргетинг с персональным оффером',
            'Дорого': 'Показать цену «в месяц», добавить рассрочку',
            'Нашёл дешевле у конкурента': 'Сравнительная таблица с конкурентами',
            'Не понял, что входит': 'Добавить чеклист покрытия и тултипы',
            'Долго грузилось': 'Оптимизировать скорость загрузки страниц',
            'Техническая ошибка': 'Срочно проверить логи и исправить баги',
            'Проблема с картой': 'Добавить больше способов оплаты',
            'Передумал в последний момент': 'Напоминание в СберБанк Онлайн через 1 час',
            'Технический сбой': 'Мониторинг ошибок + fallback-сценарии',
            '—': 'Настроить детальное логирование причин отвалов'
        }
        
        rec_text = recommendations.get(main_drop['top_reason'], 'Провести юзабилити-тесты')
        st.info(f"**Рекомендация:** {rec_text}")

st.divider()

# Графики
col1, col2 = st.columns(2)

# Воронка
funnel_counts = df.groupby('funnel_stage')['user_id'].nunique().sort_values(ascending=False)
df_funnel = pd.DataFrame({'Этап': funnel_counts.index, 'Количество': funnel_counts.values})
fig_funnel = px.funnel(df_funnel, x='Количество', y='Этап', color='Этап',
                       color_discrete_sequence=px.colors.sequential.YlGnBu,
                       title="Воронка продаж")
fig_funnel.update_layout(showlegend=False, height=380)
col1.plotly_chart(fig_funnel, use_container_width=True)

# Причины отвалов
drop_df = df[df['drop_reason'].notna()]
if len(drop_df) > 0:
    drop_counts = drop_df['drop_reason'].value_counts().head(5)
    fig_pie = px.pie(names=drop_counts.index, values=drop_counts.values,
                     title="Топ-5 причин отвалов", hole=0.4,
                     color_discrete_sequence=px.colors.sequential.YlGn)
    fig_pie.update_layout(height=380)
    col2.plotly_chart(fig_pie, use_container_width=True)
else:
    col2.info("Нет данных по отвалам")


st.subheader("Детальная аналитика")

# Вкладки для переключения между визуализациями
tab1, tab2 = st.tabs(["Сезонность", "По регионам"])

# Сезонность конверсии (месяц - день недели)
with tab1:
    # Добавляем день недели для анализа
    df_plot = df.copy()
    df_plot['dayofweek'] = df_plot['date'].dt.dayofweek
    
    # Группировка: месяц × день недели → конверсия
    seasonal_conv = df_plot.groupby(['month', 'dayofweek']).apply(
        lambda x: (x['funnel_stage'] == 'paid').sum() / len(x) * 100 if len(x) > 0 else 0
    ).reset_index(name='conversion_rate')
    
    # Pivot для heatmap
    seasonal_pivot = seasonal_conv.pivot(
        index='month', 
        columns='dayofweek', 
        values='conversion_rate'
    ).fillna(0)
    
    # Подписи осей
    month_labels = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек']
    day_labels = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
    
    fig_seasonal = px.imshow(
        seasonal_pivot.values,
        x=day_labels,
        y=month_labels,
        color_continuous_scale=px.colors.sequential.YlGn,
        title="Конверсия по месяцам и дням недели (%)",
        aspect="auto",
        labels=dict(x="День недели", y="Месяц", color="Конверсия, %")
    )
    fig_seasonal.update_layout(height=400, margin=dict(t=40, b=20, l=20, r=20))
    st.plotly_chart(fig_seasonal, use_container_width=True)
    st.caption("Подсказка: тёмно-зелёные ячейки = пик конверсии. Планируй рекламу в эти периоды.")
    

with tab2:
    region_conv = df.groupby('region').apply(
        lambda x: (x['funnel_stage'] == 'paid').sum() / len(x) * 100 if len(x) > 0 else 0
    ).sort_values(ascending=True).reset_index(name='conversion_rate')
    
    fig_region_conv = px.bar(
        region_conv,
        y='region',
        x='conversion_rate',
        orientation='h',
        title='Конверсия по регионам (%)',
        color='conversion_rate',
        color_continuous_scale=px.colors.sequential.YlGn,
        text_auto='.1f',
        height=300
    )
    fig_region_conv.update_layout(
        showlegend=False,
        margin=dict(t=40, b=20, l=20, r=20),
        xaxis_title='Конверсия, %',
        yaxis_title=''
    )
    st.plotly_chart(fig_region_conv, use_container_width=True)
    
    region_stats = df.groupby('region').agg(
        users=('user_id', 'count'),
        converted=('is_converted', 'sum'),
        avg_premium=('premium_rub', lambda x: x[x > 0].mean() if (x > 0).any() else 0),
        top_reason=('drop_reason', lambda x: x.value_counts().index[0] if x.notna().any() else '—')
    ).round(1)
    
    region_stats['conversion_rate'] = (region_stats['converted'] / region_stats['users'] * 100).round(1)
    region_stats = region_stats[['users', 'converted', 'conversion_rate', 'avg_premium', 'top_reason']]
    region_stats.columns = ['Пользователи', 'Купили', 'Конверсия, %', 'Средний чек, ₽', 'Топ-причина отвалов']
    
    region_stats = region_stats.reset_index()
    st.dataframe(
    region_stats.style.format({
        'Конверсия, %': '{:.1f}%',
        'Средний чек, ₽': '{:,.0f} ₽'
    }).background_gradient(subset=['Конверсия, %'], cmap='YlGn', axis=0),
    use_container_width=True,
    hide_index=True
    )

    best_region = region_conv.loc[region_conv['conversion_rate'].idxmax()]
    worst_region = region_conv.loc[region_conv['conversion_rate'].idxmin()]
    st.caption(
        f"Подсказка: лучшая конверсия в **{best_region['region']}** ({best_region['conversion_rate']:.1f}%), "
        f"худшая — в **{worst_region['region']}** ({worst_region['conversion_rate']:.1f}%). "
        f"Рекомендуем изучить опыт {best_region['region']} для масштабирования."
    )

# Блок рекомендаций
st.subheader("Рекомендации к действию")
for priority, metric_val, problem, action, expected in recs:
    with st.expander(f"{priority} | {metric_val}"):
        st.markdown(f"**Проблема:** {problem}")
        st.markdown(f"**Действие:** {action}")
        st.markdown(f"*Ожидаемый эффект: {expected}*")

st.divider()
st.caption("Кейс для отбора на стажировку в Сбер | Паршева Ольга")