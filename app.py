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
    df = pd.read_csv('sber_mortgage_insurance_funnel.csv', parse_dates=['date'])
    metrics_df = pd.read_csv('metrics_summary.csv')
    return df, metrics_df

df, metrics_df = load_data()

def safe_float(val):
    try: return float(val)
    except: return val

# === СЛОВАРЬ ПЕРЕВОДОВ ===
STAGE_RU = {
    'impression': 'Показ',
    'click': 'Клик',
    'form_start': 'Начало формы',
    'form_complete': 'Форма заполнена',
    'price_view': 'Просмотр цены',
    'payment_start': 'Начало оплаты',
    'paid': 'Покупка'
}
STAGES_ORDER = list(STAGE_RU.keys())

# === ФИЛЬТР ПО РЕГИОНУ (добавлено) ===
st.title("Ипотечное страхование недвижимости в Сбере")
st.caption("Аналитика воронки продаж | 4 ключевые метрики | Система принятия решений")

# Выпадающий фильтр региона
selected_region = st.selectbox(
    "📍 Фильтр по региону:",
    options=["Все регионы"] + sorted(df['region'].unique().tolist()),
    index=0,  # по умолчанию "Все регионы"
    label_visibility="collapsed"  # скрыть лейбл, если нужно
)

# Применяем фильтр к данным
if selected_region == "Все регионы":
    df_filtered = df.copy()
else:
    df_filtered = df[df['region'] == selected_region].copy()

# === МЕТРИКИ (на отфильтрованных данных) ===
# Пересчитываем метрики динамически
CONV = df_filtered['is_converted'].mean() * 100 if len(df_filtered) > 0 else 0
CONV_COUNT = int(df_filtered['is_converted'].sum())
AVG_CHECK = df_filtered[df_filtered['is_converted'] == 1]['premium_rub'].mean() if df_filtered['is_converted'].sum() > 0 else 0
GWP = df_filtered[df_filtered['is_converted'] == 1]['premium_rub'].sum() if df_filtered['is_converted'].sum() > 0 else 0

# Отображение метрик
c1, c2, c3, c4 = st.columns(4)
c1.metric("Конверсия", f"{CONV:.1f}%")
c2.metric("Купившие", f"{CONV_COUNT:,}")
c3.metric("Средний чек", f"{AVG_CHECK:,.0f} ₽")
c4.metric("Сборы (GWP)", f"{GWP:,.0f} ₽")

# === РЕКОМЕНДАЦИИ (на отфильтрованных данных) ===
def get_recommendations(conv, conv_count, avg_check, gwp, df_filt):
    recs = []
    if conv < 5.0:
        recs.append(('HIGH', f'Конверсия: {conv:.1f}%', 'Критически низкая конверсия воронки', 
                     'Запустить срочный A/B-тест: упрощённая форма + автозаполнение', '+3–5 п.п. к конверсии'))
    elif conv < 7.0:
        recs.append(('MEDIUM', f'Конверсия: {conv:.1f}%', 'Ниже целевого уровня', 
                     'Проанализировать точки оттока + провести юзабилити-тесты', '+1–3 п.п.'))
        
    expected_conv_count = len(df_filt) * 0.085
    if expected_conv_count > 0 and conv_count < expected_conv_count * 0.8:
        recs.append(('HIGH', f'Купившие: {conv_count:,}', 
                     f'Падение на {100 - conv_count/expected_conv_count*100:.0f}% к ожидаемому', 
                     'Проверить сезонность + запустить ретаргетинг в "проседающих" регионах', '+15–25% к покупкам'))
                     
    if avg_check < 17000 or avg_check > 23000:
        dev = (avg_check - 20000) / 20000 * 100 if avg_check > 0 else 0
        recs.append(('MEDIUM', f'Средний чек: {avg_check:,.0f} ₽', 
                     f'Отклонение на {dev:+.1f}% от нормы', 
                     'Проверить структуру полисов и долю онлайн-скидок', 'Стабилизация ±10%'))
                     
    expected_gwp = len(df_filt) * 0.085 * 20000
    if expected_gwp > 0 and gwp < expected_gwp * 0.85:
        recs.append(('HIGH', f'Сборы (GWP): {gwp:,.0f} ₽', 
                     f'Ниже плана на {100 - gwp/expected_gwp*100:.0f}%', 
                     'Комплекс мер: ↑конверсия + ↑чек + ↑трафик', '+10–20% к сборам'))
                     
    if not recs:
        recs.append(('OK', 'Все метрики', 'в норме', 
                     'Продолжать мониторинг и тестировать гипотезы роста', 'Стабильный рост'))
    return recs

recs = get_recommendations(CONV, CONV_COUNT, AVG_CHECK, GWP, df_filtered)

# === ГЛАВНАЯ ПРОБЛЕМА ВОРОНКИ (на отфильтрованных данных) ===
stage_counts = df_filtered.groupby('funnel_stage')['user_id'].nunique()
drop_analysis = []
for i in range(len(STAGES_ORDER) - 1):
    curr = STAGES_ORDER[i]
    next_s = STAGES_ORDER[i + 1]
    curr_count = stage_counts.get(curr, 0)
    next_count = stage_counts.get(next_s, 0)
    if curr_count > 0:
        drop_count = curr_count - next_count
        drop_rate = (drop_count / curr_count) * 100
        drop_analysis.append({
            'from_stage': curr,
            'to_stage': next_s,
            'drop_rate': drop_rate,
            'drop_count': drop_count
        })

if drop_analysis and len(df_filtered) > 0:
    main_drop = max(drop_analysis, key=lambda x: x['drop_rate'])
    st.subheader("Главная проблема воронки")
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.metric(
            label="Максимальный отвал",
            value=f"{main_drop['drop_rate']:.1f}%",
            delta=f"-{main_drop['drop_count']:,.0f} пользователей"
        )
        st.markdown(f"**Этап:** {STAGE_RU[main_drop['from_stage']]}")
        st.markdown(f"**Переход:** → {STAGE_RU[main_drop['to_stage']]}")
    
    with col2:
        st.markdown("###### Что делать?")
        st.info(f"**Рекомендация:** Провести детальный анализ поведения пользователей на этапе «{STAGE_RU[main_drop['from_stage']]}»: проверить скорость загрузки, упростить интерфейс, протестировать гипотезы.")

st.divider()

# === ГРАФИКИ (на отфильтрованных данных) ===
col1, col2 = st.columns(2)

# Воронка с переключателем
funnel_type = st.radio(
    "Тип воронки:",
    options=["Накопительная", "Точечная"],
    horizontal=True,
    label_visibility="collapsed"
)
st.caption("**Накопительная**: сколько дошло до этапа и дальше. **Точечная**: где именно пользователи отвалились.")

point_counts = df_filtered.groupby('funnel_stage')['user_id'].nunique()

if funnel_type == "Накопительная":
    cumulative_counts = {}
    for i, stage in enumerate(STAGES_ORDER):
        stages_included = STAGES_ORDER[i:]
        cumulative_counts[stage] = sum(point_counts.get(s, 0) for s in stages_included)
    df_funnel = pd.DataFrame({
        'Этап': [STAGE_RU[s] for s in STAGES_ORDER],
        'Количество': [cumulative_counts[s] for s in STAGES_ORDER]
    })
    title = "Воронка продаж (накопительная)"
else:
    df_funnel = pd.DataFrame({
        'Этап': [STAGE_RU[s] for s in STAGES_ORDER],
        'Количество': [point_counts.get(s, 0) for s in STAGES_ORDER]
    })
    title = "Воронка продаж (точечная)"

fig_funnel = px.funnel(
    df_funnel, x='Количество', y='Этап', color='Этап',
    color_discrete_sequence=px.colors.sequential.YlGnBu, title=title,
    category_orders={'Этап': [STAGE_RU[s] for s in STAGES_ORDER]}
)
fig_funnel.update_layout(showlegend=False, height=380)
col1.plotly_chart(fig_funnel, use_container_width=True)

# Конверсия по устройствам
if len(df_filtered) > 0:
    device_conv = df_filtered.groupby('device').apply(
        lambda x: (x['funnel_stage'] == 'paid').sum() / len(x) * 100 if len(x) > 0 else 0
    ).reset_index(name='conversion_rate')

    fig_device = px.pie(
        device_conv, 
        names='device', 
        values='conversion_rate',
        title="Конверсия по устройствам (%)", 
        hole=0.4,
        color_discrete_sequence=px.colors.sequential.YlGn
    )
    fig_device.update_traces(textinfo='percent+label')
    fig_device.update_layout(height=380)
    col2.plotly_chart(fig_device, use_container_width=True)
else:
    col2.info("Нет данных для выбранного региона")

# === ДЕТАЛЬНАЯ АНАЛИТИКА ===
st.subheader("Детальная аналитика")
tab1, tab2 = st.tabs(["Сезонность", "По регионам"])

with tab1:
    if len(df_filtered) > 0:
        df_plot = df_filtered.copy()
        df_plot['dayofweek'] = df_plot['date'].dt.dayofweek
        seasonal_conv = df_plot.groupby(['month', 'dayofweek']).apply(
            lambda x: (x['funnel_stage'] == 'paid').sum() / len(x) * 100 if len(x) > 0 else 0
        ).reset_index(name='conversion_rate')
        
        if len(seasonal_conv) > 0:
            seasonal_pivot = seasonal_conv.pivot(index='month', columns='dayofweek', values='conversion_rate').fillna(0)
            month_labels = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек']
            day_labels = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
            
            fig_seasonal = px.imshow(
                seasonal_pivot.values, x=day_labels, y=month_labels,
                color_continuous_scale=px.colors.sequential.YlGn,
                title=f"Конверсия по месяцам и дням недели (%) {f'• {selected_region}' if selected_region != 'Все регионы' else ''}",
                aspect="auto", labels=dict(x="День недели", y="Месяц", color="Конверсия, %")
            )
            fig_seasonal.update_layout(height=400, margin=dict(t=40, b=20, l=20, r=20))
            st.plotly_chart(fig_seasonal, use_container_width=True)
            st.caption("Подсказка: тёмно-зелёные ячейки = пик конверсии. Планируйте рекламу в эти периоды.")
        else:
            st.info("Недостаточно данных для построения тепловой карты")
    else:
        st.info("Нет данных для выбранного региона")

with tab2:
    if selected_region == "Все регионы" and len(df_filtered) > 0:
        # Показываем сравнение по регионам только если выбрано "Все регионы"
        region_conv = df_filtered.groupby('region').apply(
            lambda x: (x['funnel_stage'] == 'paid').sum() / len(x) * 100 if len(x) > 0 else 0
        ).sort_values(ascending=True).reset_index(name='conversion_rate')
        
        fig_region = px.bar(
            region_conv, y='region', x='conversion_rate', orientation='h',
            title='Конверсия по регионам (%)', color='conversion_rate',
            color_continuous_scale=px.colors.sequential.YlGn, text_auto='.1f', height=300
        )
        fig_region.update_layout(showlegend=False, margin=dict(t=40, b=20, l=20, r=20), xaxis_title='Конверсия, %', yaxis_title='')
        st.plotly_chart(fig_region, use_container_width=True)
        
        # Таблица по регионам
        region_stats = df_filtered.groupby('region').agg(
            users=('user_id', 'count'),
            converted=('is_converted', 'sum'),
            avg_premium=('premium_rub', lambda x: x[x > 0].mean() if (x > 0).any() else 0)
        ).round(1)
        region_stats['conversion_rate'] = (region_stats['converted'] / region_stats['users'] * 100).round(1)
        region_stats = region_stats[['users', 'converted', 'conversion_rate', 'avg_premium']]
        region_stats.columns = ['Пользователи', 'Купили', 'Конверсия, %', 'Средний чек, ₽']
        region_stats = region_stats.reset_index()
        
        st.dataframe(
            region_stats.style.format({'Конверсия, %': '{:.1f}%', 'Средний чек, ₽': '{:,.0f} ₽'})
            .background_gradient(subset=['Конверсия, %'], cmap='YlGn', axis=0),
            use_container_width=True, hide_index=True
        )
        
        best = region_conv.loc[region_conv['conversion_rate'].idxmax()]
        worst = region_conv.loc[region_conv['conversion_rate'].idxmin()]
        st.caption(f"Лучшая конверсия: **{best['region']}** ({best['conversion_rate']:.1f}%). Худшая: **{worst['region']}** ({worst['conversion_rate']:.1f}%).")
    else:
        # Если выбран конкретный регион — показываем его детали
        # if len(df_filtered) > 0:
        #     st.markdown(f"### 📊 Детали по региону: **{selected_region}**")
        #     c1, c2, c3 = st.columns(3)
        #     c1.metric("Пользователи", f"{len(df_filtered):,}")
        #     c2.metric("Конверсия", f"{CONV:.1f}%")
        #     c3.metric("Средний чек", f"{AVG_CHECK:,.0f} ₽")
            
        #     # Конверсия по устройствам в этом регионе
        #     device_stats = df_filtered.groupby('device').agg(
        #         users=('user_id', 'count'),
        #         converted=('is_converted', 'sum')
        #     )
        #     device_stats['conv_rate'] = (device_stats['converted'] / device_stats['users'] * 100).round(1)
        #     st.dataframe(
        #         device_stats[['users', 'converted', 'conv_rate']].rename(
        #             columns={'users': 'Пользователи', 'converted': 'Купили', 'conv_rate': 'Конверсия, %'}
        #         ).style.format({'Конверсия, %': '{:.1f}%'}),
        #         hide_index=True
        #     )
        # else:
        #     st.info("Нет данных для выбранного региона")
        if len(df_filtered) > 0:
            st.markdown(f"### Детали по региону: **{selected_region}**")
            c1, c2, c3 = st.columns(3)
            c1.metric("Пользователи", f"{len(df_filtered):,}")
            c2.metric("Конверсия", f"{CONV:.1f}%")
            c3.metric("Средний чек", f"{AVG_CHECK:,.0f} ₽")
            
            # Конверсия по устройствам в этом регионе
            device_stats = df_filtered.groupby('device').agg(
                users=('user_id', 'count'),
                converted=('is_converted', 'sum')
            ).reset_index()
            
            device_stats['conv_rate'] = (device_stats['converted'] / device_stats['users'] * 100).round(1)
            
            # Переводим названия устройств на русский
            device_labels = {
                'mobile': 'Mobile',
                'desktop': 'Desktop'
            }
            device_stats['Устройство'] = device_stats['device'].map(device_labels)
            
            st.dataframe(
                device_stats[['Устройство', 'users', 'converted', 'conv_rate']].rename(
                    columns={'users': 'Пользователи', 'converted': 'Купили', 'conv_rate': 'Конверсия, %'}
                ).style.format({'Конверсия, %': '{:.1f}%'}),
                hide_index=True,
                use_container_width=True
            )
            
            # Добавляем инсайт
            if len(device_stats) == 2:
                mobile_conv = device_stats[device_stats['device'] == 'mobile']['conv_rate'].values[0]
                desktop_conv = device_stats[device_stats['device'] == 'desktop']['conv_rate'].values[0]
                gap = desktop_conv - mobile_conv
                if gap > 1.0:
                    st.warning(f"**Разрыв в конверсии**: desktop превосходит mobile на {gap:.1f} п.п. Рекомендуется оптимизировать мобильную версию.")

# st.subheader("Рекомендации к действию")
# for priority, metric_val, problem, action, expected in recs:
#     with st.expander(f"{priority} | {metric_val}"):
#         st.markdown(f"**Проблема:** {problem}")
#         st.markdown(f"**Действие:** {action}")
#         st.markdown(f"*Ожидаемый эффект: {expected}*")

st.divider()
st.caption("Кейс для отбора на стажировку в Сбер | Паршева Ольга")