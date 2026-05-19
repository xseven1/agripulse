import json
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ── THEME ──────────────────────────────────────────────────────────────────────
GOLD    = '#B8730A'
GREEN   = '#1A6E3C'
RED     = '#C0392B'
BLUE    = '#1A5C9E'
PURPLE  = '#7B3FA0'
ORANGE  = '#C0650A'
TEAL    = '#0E7C6E'
MUTED   = '#9BA3B8'
SUB     = '#5A6077'
WHITE   = '#1A1D2E'
PLOT_BG = '#FFFFFF'
GRID    = '#EEF0F5'
BAND    = 'rgba(184,115,10,0.10)'
CARD_BG = 'rgba(0,0,0,0)'

PRIMAL_COLORS = [GOLD, BLUE, GREEN, RED, PURPLE, ORANGE, TEAL, '#FF70B0']

LAYOUT_BASE = dict(
    paper_bgcolor=CARD_BG,
    plot_bgcolor=PLOT_BG,
    font=dict(color=WHITE, family='DM Sans, Inter, sans-serif', size=11),
    margin=dict(l=8, r=8, t=12, b=8),
    legend=dict(
        orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
        bgcolor='rgba(0,0,0,0)', font=dict(size=10, color=WHITE),
    ),
    xaxis=dict(showgrid=False, color=SUB, linecolor=MUTED,
               tickfont=dict(color=SUB, size=10)),
    yaxis=dict(showgrid=True, gridcolor=GRID, color=SUB,
               tickfont=dict(color=SUB, size=10)),
    hovermode='x unified',
    hoverlabel=dict(bgcolor='#1C2333', bordercolor='rgba(255,255,255,0.15)',
                    font=dict(color=WHITE, size=11)),
)

MON_TICKS = dict(
    tickvals=[1,32,60,91,121,152,182,213,244,274,305,335],
    ticktext=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
)


def to_json(fig):
    return json.loads(fig.to_json())


def _L(height=300, yprefix='', ysuffix='', **kwargs):
    d = {**LAYOUT_BASE, 'height': height}
    if yprefix or ysuffix:
        d['yaxis'] = {**LAYOUT_BASE['yaxis'], 'tickprefix': yprefix, 'ticksuffix': ysuffix}
    d.update(kwargs)
    return d


def _band(fig, df, y_col, curr_yr, doy_col='doy', n_years=5):
    """Add 5-year historical range band to a figure."""
    band_years = [y for y in df['Year'].unique() if curr_yr - n_years - 1 <= y <= curr_yr - 1]
    band_data = {}
    for yr in band_years:
        for _, row in df[df['Year'] == yr].iterrows():
            d = int(row[doy_col])
            band_data.setdefault(d, []).append(row[y_col])
    if not band_data:
        return fig
    doys = sorted(band_data)
    y_min = [np.percentile(band_data[d], 10) for d in doys]
    y_max = [np.percentile(band_data[d], 90) for d in doys]
    fig.add_trace(go.Scatter(
        x=doys + doys[::-1], y=y_max + y_min[::-1],
        fill='toself', fillcolor=BAND,
        line=dict(color='rgba(0,0,0,0)'),
        name='5-yr range', hoverinfo='skip', showlegend=True,
    ))
    return fig


def _slice_period(df, date_col, period='year'):
    """Slice dataframe to the requested period."""
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    max_date = df[date_col].max()
    if period == 'week':
        cutoff = max_date - pd.Timedelta(weeks=6)
    elif period == 'month':
        cutoff = max_date - pd.Timedelta(weeks=13)
    else:  # year
        cutoff = max_date - pd.Timedelta(weeks=54)
    return df[df[date_col] >= cutoff]


def _period_xaxis(period):
    """Return appropriate x-axis tick settings for a given period."""
    if period == 'week':
        return dict(
            tickformat='%b %d',
            dtick=7 * 24 * 60 * 60 * 1000,  # 1 week in ms
            tickangle=-30,
            showgrid=True,
            gridcolor=GRID,
            tickfont=dict(color=SUB, size=10),
        )
    elif period == 'month':
        return dict(
            tickformat='%b %d',
            dtick=14 * 24 * 60 * 60 * 1000,  # 2 weeks in ms
            tickangle=-30,
            showgrid=True,
            gridcolor=GRID,
            tickfont=dict(color=SUB, size=10),
        )
    else:  # year
        return dict(
            tickformat='%b %y',
            dtick='M2',  # every 2 months
            showgrid=False,
            tickfont=dict(color=SUB, size=10),
        )


def _drop_partial(df, y_col, threshold=0.6):
    """Drop last row if it looks like a partial week artifact."""
    if len(df) > 4:
        median = df[y_col].iloc[:-1].median()
        if pd.notna(median) and median > 0 and df[y_col].iloc[-1] < median * threshold:
            return df.iloc[:-1].copy()
    return df


# ══════════════════════════════════════════════════════════════════════════════
# SLAUGHTER MODULE
# ══════════════════════════════════════════════════════════════════════════════

def _prep_slaughter(df):
    df = df.copy()
    df['slaughter_date'] = pd.to_datetime(df['slaughter_date'], errors='coerce')
    df['week_start'] = df['slaughter_date'] - pd.to_timedelta(df['slaughter_date'].dt.weekday, unit='D')
    df['commodity'] = df['commodity'].replace({'Slaughter Hogs': 'Hogs', 'Slaughter Cattle': 'Cattle'})
    df = df[df['period'] == 'Current'].dropna(subset=['week_start', 'slaughter'])
    df['Year'] = df['week_start'].dt.year
    weekly = df.groupby(['commodity', 'week_start', 'Year'])['slaughter'].sum().reset_index()
    weekly.rename(columns={'slaughter': 'count'}, inplace=True)
    weekly['doy'] = weekly['week_start'].dt.dayofyear
    weekly['iso_week'] = weekly['week_start'].apply(lambda x: x.isocalendar().week)
    return weekly.sort_values('week_start')


def chart_slaughter_seasonal(df, commodity='Cattle', color=GOLD, height=310):
    """Grouped bar chart — this year vs year ago side by side."""
    w = _prep_slaughter(df)
    sub = w[w['commodity'] == commodity]
    curr_yr = sub['Year'].max()
    curr = _drop_partial(sub[sub['Year'] == curr_yr].sort_values('week_start'), 'count')
    prev = sub[sub['Year'] == curr_yr - 1].sort_values('week_start')

    merged = curr.merge(prev[['iso_week', 'count']], on='iso_week', suffixes=('_curr', '_prev'), how='left')
    merged = merged.sort_values('week_start')

    bar_color = GOLD if commodity == 'Cattle' else BLUE

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=merged['week_start'], y=merged['count_curr'],
        name=str(curr_yr),
        marker_color=bar_color,
        marker_line_width=0,
        hovertemplate='%{x|%b %d}<br>%{y:,.0f} head<extra>' + str(curr_yr) + '</extra>',
    ))
    fig.add_trace(go.Bar(
        x=merged['week_start'], y=merged['count_prev'],
        name=str(curr_yr - 1),
        marker_color=MUTED,
        marker_line_width=0,
        opacity=0.7,
        hovertemplate='%{x|%b %d}<br>%{y:,.0f} head<extra>' + str(curr_yr - 1) + '</extra>',
    ))
    fig.update_layout(**_L(height=height, barmode='group'))
    fig.update_xaxes(tickformat="%b '%y", tickfont=dict(color=SUB, size=10))
    fig.update_yaxes(tickformat=',.0f', title_text='Head')
    return to_json(fig)


def chart_slaughter_yoy_pct(df, commodity='Cattle', height=280):
    """YoY % change bar — green above, red below."""
    w = _prep_slaughter(df)
    sub = w[w['commodity'] == commodity]
    curr_yr = sub['Year'].max()
    c = sub[sub['Year'] == curr_yr].copy()
    p = sub[sub['Year'] == curr_yr - 1].copy()
    merged = c.merge(p[['iso_week', 'count']], on='iso_week', suffixes=('', '_prev')).dropna(subset=['count_prev'])
    merged['pct'] = (merged['count'] - merged['count_prev']) / merged['count_prev'] * 100

    fig = go.Figure(go.Bar(
        x=merged['iso_week'], y=merged['pct'],
        marker_color=[GREEN if v >= 0 else RED for v in merged['pct']],
        marker_line_width=0,
        hovertemplate='Week %{x}: %{y:.1f}%<extra></extra>',
    ))
    fig.add_hline(y=0, line_color='rgba(255,255,255,0.2)', line_width=1)
    fig.update_layout(**_L(height=height, ysuffix='%'))
    fig.update_xaxes(title_text='Week of Year', color=SUB, title_font=dict(size=10))
    return to_json(fig)


def chart_hogs_vs_cattle(df, height=310):
    """Both species % change vs year ago on one chart."""
    w = _prep_slaughter(df)
    curr_yr = w['Year'].max()
    fig = go.Figure()
    for commodity, color in [('Cattle', GOLD), ('Hogs', BLUE)]:
        sub = w[w['commodity'] == commodity]
        c = sub[sub['Year'] == curr_yr].copy()
        p = sub[sub['Year'] == curr_yr - 1].copy()
        merged = c.merge(p[['iso_week', 'count']], on='iso_week', suffixes=('', '_prev')).dropna(subset=['count_prev'])
        merged['pct'] = (merged['count'] - merged['count_prev']) / merged['count_prev'] * 100
        merged = _drop_partial(merged, 'pct')
        fig.add_trace(go.Scatter(
            x=merged['doy'], y=merged['pct'],
            mode='lines', name=commodity,
            line=dict(color=color, width=2.5),
            connectgaps=False,
            hovertemplate=f'{commodity}: %{{y:.1f}}%<extra></extra>',
        ))
    fig.add_hline(y=0, line_color='rgba(255,255,255,0.2)', line_width=1.5)
    fig.update_layout(**_L(height=height, ysuffix='%'))
    fig.update_xaxes(**MON_TICKS)
    return to_json(fig)


def chart_cow_slaughter(cow_df, height=310):
    """Dairy vs Other cow slaughter — herd liquidation signal."""
    cow_df = cow_df.copy()
    cow_df['report_date'] = pd.to_datetime(cow_df['report_date'], errors='coerce')
    cow_df['week_start'] = cow_df['report_date'] - pd.to_timedelta(cow_df['report_date'].dt.weekday, unit='D')
    cow_df['Year'] = cow_df['week_start'].dt.year
    # class column may come as 'class' or 'class_name'
    cls_col = 'class_name' if 'class_name' in cow_df.columns else 'class'
    cow_df = cow_df[cow_df[cls_col].isin(['Dairy Cows', 'Other Cows'])].dropna(subset=['volume'])
    # Remove obvious outliers (volume < 1000)
    cow_df = cow_df[cow_df['volume'] > 1000]
    w = cow_df.groupby([cls_col, 'week_start', 'Year'])['volume'].sum().reset_index()
    w['doy'] = w['week_start'].dt.dayofyear
    curr_yr = w['Year'].max()

    fig = go.Figure()
    for cls, color in [('Dairy Cows', BLUE), ('Other Cows', ORANGE)]:
        sub = w[(w[cls_col] == cls) & (w['Year'] == curr_yr)].sort_values('week_start')
        sub = _drop_partial(sub, 'volume')
        fig.add_trace(go.Scatter(
            x=sub['doy'], y=sub['volume'],
            mode='lines+markers', name=cls,
            line=dict(color=color, width=2.5), marker=dict(size=4),
            connectgaps=False,
            hovertemplate=f'{cls}: %{{y:,.0f}}<extra></extra>',
        ))
    fig.update_layout(**_L(height=height))
    fig.update_xaxes(**MON_TICKS)
    fig.update_yaxes(tickformat=',.0f')
    return to_json(fig)


def chart_ytd_slaughter(df, commodity='Cattle', height=290):
    """YTD cumulative slaughter this year."""
    w = _prep_slaughter(df)
    sub = w[w['commodity'] == commodity]
    curr_yr = sub['Year'].max()
    curr = sub[sub['Year'] == curr_yr].sort_values('week_start').copy()
    prev = sub[sub['Year'] == curr_yr - 1].sort_values('week_start').copy()
    curr = _drop_partial(curr, 'count')
    curr['cum'] = curr['count'].cumsum()
    prev['cum'] = prev['count'].cumsum()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=curr['doy'], y=curr['cum'],
        mode='lines+markers', name=str(curr_yr),
        line=dict(color=GOLD, width=2.5), marker=dict(size=4),
        connectgaps=False, hovertemplate='%{y:,.0f} head<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=prev['doy'], y=prev['cum'],
        mode='lines', name=str(curr_yr - 1),
        line=dict(color=MUTED, width=1.5, dash='dot'),
        connectgaps=False, hovertemplate='%{y:,.0f} head<extra></extra>',
    ))
    fig.update_layout(**_L(height=height))
    fig.update_xaxes(**MON_TICKS)
    fig.update_yaxes(tickformat='.2s')
    return to_json(fig)


def chart_implied_production(slaughter_df, carcass_df, commodity='Cattle', height=290):
    """Head × avg carcass weight = implied lbs produced."""
    w = _prep_slaughter(slaughter_df)
    sub = w[w['commodity'] == commodity]
    curr_yr = sub['Year'].max()
    s = sub[sub['Year'] == curr_yr].sort_values('week_start').copy()
    s['iso_week'] = s['week_start'].apply(lambda x: x.isocalendar().week)

    cw = carcass_df.copy()
    cw['report_date'] = pd.to_datetime(cw['report_date'], errors='coerce')
    cw['week_start'] = cw['report_date'] - pd.to_timedelta(cw['report_date'].dt.weekday, unit='D')
    cw['Year'] = cw['week_start'].dt.year
    cw_curr = cw[(cw['Year'] == curr_yr) & (cw['purchase_type'] == 'Prod. Sold (All Purchase Types)')].copy()
    cw_curr['iso_week'] = cw_curr['week_start'].apply(lambda x: x.isocalendar().week)
    cw_agg = cw_curr.groupby('iso_week')['avg_carcass_weight'].mean().reset_index()

    merged = s.merge(cw_agg, on='iso_week', how='left')
    merged['lbs'] = merged['count'] * merged['avg_carcass_weight']
    merged = _drop_partial(merged, 'lbs')

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=merged['doy'], y=merged['lbs'] / 1e6,
        mode='lines+markers', name='Implied Production',
        line=dict(color=GOLD, width=2.5), marker=dict(size=4),
        connectgaps=False, hovertemplate='%{y:.1f}M lbs<extra></extra>',
    ))
    fig.update_layout(**_L(height=height, ysuffix='M lbs'))
    fig.update_xaxes(**MON_TICKS)
    return to_json(fig)


def chart_carcass_weights(carcass_df, height=290):
    """Carcass weight trend with 5-year band."""
    cw = carcass_df.copy()
    cw['report_date'] = pd.to_datetime(cw['report_date'], errors='coerce')
    cw['week_start'] = cw['report_date'] - pd.to_timedelta(cw['report_date'].dt.weekday, unit='D')
    cw['Year'] = cw['week_start'].dt.year
    cw = cw[cw['purchase_type'] == 'Prod. Sold (All Purchase Types)'].dropna(subset=['avg_carcass_weight'])
    weekly = cw.groupby(['week_start', 'Year'])['avg_carcass_weight'].mean().reset_index().sort_values('week_start')
    weekly['doy'] = weekly['week_start'].dt.dayofyear
    curr_yr = weekly['Year'].max()
    curr = _drop_partial(weekly[weekly['Year'] == curr_yr].copy(), 'avg_carcass_weight')
    curr['roll4'] = curr['avg_carcass_weight'].rolling(4, min_periods=1).mean()

    fig = go.Figure()
    fig = _band(fig, weekly, 'avg_carcass_weight', curr_yr)
    fig.add_trace(go.Scatter(
        x=curr['doy'], y=curr['avg_carcass_weight'],
        mode='lines+markers', name=str(curr_yr),
        line=dict(color=GOLD, width=2.5), marker=dict(size=4),
        connectgaps=False, hovertemplate='%{y:.1f} lbs<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=curr['doy'], y=curr['roll4'],
        mode='lines', name='4-wk avg',
        line=dict(color=TEAL, width=1.5, dash='dot'),
        connectgaps=False, hovertemplate='4-wk: %{y:.1f} lbs<extra></extra>',
    ))
    fig.update_layout(**_L(height=height, ysuffix=' lbs'))
    fig.update_xaxes(**MON_TICKS)
    return to_json(fig)


# ══════════════════════════════════════════════════════════════════════════════
# CUTOUT MODULE
# ══════════════════════════════════════════════════════════════════════════════

def _prep_cutout(df):
    df = df.copy()
    df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')
    df['week_start'] = df['report_date'] - pd.to_timedelta(df['report_date'].dt.weekday, unit='D')
    df['Year'] = df['week_start'].dt.year
    df = df.rename(columns={'Attribute': 'attribute', 'Value': 'value'})
    weekly = df.groupby(['attribute', 'week_start', 'Year'])['value'].mean().reset_index()
    weekly['doy'] = weekly['week_start'].dt.dayofyear
    weekly['iso_week'] = weekly['week_start'].apply(lambda x: x.isocalendar().week)
    return weekly.sort_values('week_start')


def chart_cutout_seasonal(cutout_df, height=310):
    """Choice & Select vs 5-year band."""
    w = _prep_cutout(cutout_df)
    curr_yr = w['Year'].max()
    fig = go.Figure()
    for attr, color in [('Choice', GOLD), ('Select', BLUE)]:
        sub = w[w['attribute'] == attr]
        curr = _drop_partial(sub[sub['Year'] == curr_yr].sort_values('week_start').copy(), 'value')
        fig = _band(fig, sub, 'value', curr_yr)
        fig.add_trace(go.Scatter(
            x=curr['doy'], y=curr['value'],
            mode='lines+markers', name=f'{attr} {curr_yr}',
            line=dict(color=color, width=2.5), marker=dict(size=4),
            connectgaps=False,
            hovertemplate=f'{attr}: $%{{y:.2f}}<extra></extra>',
        ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(**MON_TICKS)
    return to_json(fig)


def chart_choice_select_spread(cutout_df, height=290):
    """Choice minus Select spread with historical average line."""
    w = _prep_cutout(cutout_df)
    curr_yr = w['Year'].max()
    ch = w[(w['attribute'] == 'Choice') & (w['Year'] == curr_yr)].set_index('week_start')['value']
    se = w[(w['attribute'] == 'Select') & (w['Year'] == curr_yr)].set_index('week_start')['value']
    spread = (ch - se).dropna().reset_index()
    spread.columns = ['week_start', 'spread']
    spread['doy'] = pd.to_datetime(spread['week_start']).dt.dayofyear
    spread = _drop_partial(spread, 'spread', threshold=0.3)

    # Historical avg spread
    ch_all = w[w['attribute'] == 'Choice'].set_index(['week_start', 'Year'])['value']
    se_all = w[w['attribute'] == 'Select'].set_index(['week_start', 'Year'])['value']
    hist_spread = (ch_all - se_all).dropna()
    hist_avg = hist_spread[hist_spread.index.get_level_values('Year') < curr_yr].mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=spread['doy'], y=spread['spread'],
        mode='lines+markers', name='Spread',
        line=dict(color=GOLD, width=2.5), marker=dict(size=4),
        connectgaps=False, hovertemplate='Spread: $%{y:.2f}<extra></extra>',
    ))
    if not np.isnan(hist_avg):
        fig.add_hline(y=hist_avg, line_color=SUB, line_dash='dot', line_width=1.5,
                      annotation_text=f'Hist avg: ${hist_avg:.2f}',
                      annotation_font_color=SUB, annotation_position='right')
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(**MON_TICKS)
    return to_json(fig)


def chart_cutout_yoy_pct(cutout_df, attr='Choice', height=280):
    """Week-by-week % change vs year ago for one cutout attribute."""
    w = _prep_cutout(cutout_df)
    sub = w[w['attribute'] == attr]
    curr_yr = sub['Year'].max()
    c = sub[sub['Year'] == curr_yr].copy()
    p = sub[sub['Year'] == curr_yr - 1].copy()
    merged = c.merge(p[['iso_week', 'value']], on='iso_week', suffixes=('', '_prev')).dropna()
    merged['pct'] = (merged['value'] - merged['value_prev']) / merged['value_prev'] * 100

    fig = go.Figure(go.Bar(
        x=merged['iso_week'], y=merged['pct'],
        marker_color=[GREEN if v >= 0 else RED for v in merged['pct']],
        marker_line_width=0,
        hovertemplate=f'Week %{{x}}: %{{y:.1f}}%<extra>{attr}</extra>',
    ))
    fig.add_hline(y=0, line_color='rgba(255,255,255,0.2)', line_width=1)
    fig.update_layout(**_L(height=height, ysuffix='%'))
    fig.update_xaxes(title_text='Week of Year', color=SUB, title_font=dict(size=10))
    return to_json(fig)


def chart_beef_primals(primal_df, height=310):
    """Beef primal values — all cuts current year."""
    primal_df = primal_df.copy()
    primal_df['report_date'] = pd.to_datetime(primal_df['report_date'], errors='coerce')
    primal_df['week_start'] = primal_df['report_date'] - pd.to_timedelta(primal_df['report_date'].dt.weekday, unit='D')
    primal_df['Year'] = primal_df['week_start'].dt.year
    primal_df = primal_df[~primal_df['primal_desc'].isin(['Cutout', 'Trim'])].dropna(subset=['choice_600_900'])
    w = primal_df.groupby(['primal_desc', 'week_start', 'Year'])['choice_600_900'].mean().reset_index()
    w['doy'] = w['week_start'].dt.dayofyear
    curr_yr = w['Year'].max()

    fig = go.Figure()
    for i, p in enumerate(sorted(w[w['Year'] == curr_yr]['primal_desc'].unique())):
        sub = w[(w['primal_desc'] == p) & (w['Year'] == curr_yr)].sort_values('week_start')
        sub = _drop_partial(sub, 'choice_600_900')
        fig.add_trace(go.Scatter(
            x=sub['doy'], y=sub['choice_600_900'],
            mode='lines', name=p,
            line=dict(color=PRIMAL_COLORS[i % len(PRIMAL_COLORS)], width=1.8),
            connectgaps=False,
            hovertemplate=f'{p}: $%{{y:.2f}}<extra></extra>',
        ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(**MON_TICKS)
    return to_json(fig)


def chart_pork_primals(pork_df, height=310):
    """Pork primal values — all cuts current year."""
    pork_df = pork_df.copy()
    pork_df['report_date'] = pd.to_datetime(pork_df['report_date'], errors='coerce')
    pork_df['week_start'] = pork_df['report_date'] - pd.to_timedelta(pork_df['report_date'].dt.weekday, unit='D')
    pork_df['Year'] = pork_df['week_start'].dt.year
    pork_df = pork_df[~pork_df['commodity'].isin(['Total Loads', 'Carcass', 'Trim'])].dropna(subset=['value'])
    w = pork_df.groupby(['commodity', 'week_start', 'Year'])['value'].mean().reset_index()
    w['doy'] = w['week_start'].dt.dayofyear
    curr_yr = w['Year'].max()

    fig = go.Figure()
    for i, p in enumerate(sorted(w[w['Year'] == curr_yr]['commodity'].unique())):
        sub = w[(w['commodity'] == p) & (w['Year'] == curr_yr)].sort_values('week_start')
        sub = _drop_partial(sub, 'value')
        fig.add_trace(go.Scatter(
            x=sub['doy'], y=sub['value'],
            mode='lines', name=p,
            line=dict(color=PRIMAL_COLORS[i % len(PRIMAL_COLORS)], width=1.8),
            connectgaps=False,
            hovertemplate=f'{p}: $%{{y:.2f}}<extra></extra>',
        ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(**MON_TICKS)
    return to_json(fig)


def chart_seasonal_avg_cutout(cutout_df, height=290):
    """Historical average seasonal pattern for Choice and Select."""
    w = _prep_cutout(cutout_df)
    fig = go.Figure()
    for attr, color in [('Choice', GOLD), ('Select', BLUE)]:
        sub = w[w['attribute'] == attr].copy()
        avg = sub.groupby('iso_week')['value'].mean().reset_index()
        fig.add_trace(go.Scatter(
            x=avg['iso_week'], y=avg['value'],
            mode='lines', name=attr,
            line=dict(color=color, width=2.5),
            hovertemplate=f'{attr} avg: $%{{y:.2f}}<extra></extra>',
        ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(title_text='Week of Year', color=SUB, title_font=dict(size=10))
    return to_json(fig)


# ══════════════════════════════════════════════════════════════════════════════
# CASH vs FUTURES MODULE
# ══════════════════════════════════════════════════════════════════════════════

def _prep_basis(cash_df, futures_df):
    """Merge cash cattle and LE futures into basis dataframe."""
    cc = cash_df.copy()
    cc['report_date'] = pd.to_datetime(cc['report_date'], errors='coerce')
    cc = cc[cc['class_description'] == 'ALL BEEF TYPE'].copy()
    cc = cc[(cc['weighted_avg_price'] > 150) & (cc['weighted_avg_price'] < 350)]
    cc['week_start'] = cc['report_date'] - pd.to_timedelta(cc['report_date'].dt.weekday, unit='D')
    cc['Year'] = cc['report_date'].dt.year
    # Use median to suppress any flat/outlier grade rows
    cash = cc.groupby(['week_start', 'Year'])['weighted_avg_price'].median().reset_index()

    ep = futures_df.copy()
    ep['trading_day'] = pd.to_datetime(ep['trading_day'], errors='coerce')
    le = ep[ep['commodity'] == 'LE'].copy()
    month_map = {'G': 2, 'J': 4, 'M': 6, 'Q': 8, 'V': 10, 'Z': 12}
    le['month_num'] = le['month'].map(month_map)
    le = le.dropna(subset=['month_num'])
    le['expiry_approx'] = pd.to_datetime(dict(year=le['year'], month=le['month_num'].astype(int), day=15))
    le = le.sort_values(['trading_day', 'expiry_approx'])
    nearby = le[le['expiry_approx'] >= le['trading_day']].groupby('trading_day').first().reset_index()
    nearby['week_start'] = nearby['trading_day'] - pd.to_timedelta(nearby['trading_day'].dt.weekday, unit='D')
    nearby['Year'] = nearby['trading_day'].dt.year
    fut = nearby.groupby(['week_start', 'Year'])['close'].mean().reset_index()

    merged = cash.merge(fut, on=['week_start', 'Year'], how='inner')
    merged = merged[(merged['close'] > 150) & (merged['weighted_avg_price'] > 150)]
    merged = merged.sort_values('week_start')
    merged['basis'] = merged['weighted_avg_price'] - merged['close']
    merged['rolling_basis'] = merged['basis'].rolling(4, min_periods=1).mean()
    merged['doy'] = pd.to_datetime(merged['week_start']).dt.dayofyear
    merged['iso_week'] = pd.to_datetime(merged['week_start']).apply(lambda x: x.isocalendar().week)
    return merged.sort_values('week_start')


def chart_cash_vs_futures(cash_df, futures_df, height=310):
    """Cash and nearby futures on same axis."""
    basis_df = _prep_basis(cash_df, futures_df)
    curr_yr = basis_df['Year'].max()
    sub = _drop_partial(basis_df[basis_df['Year'] == curr_yr].sort_values('week_start').copy(), 'weighted_avg_price')

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sub['doy'], y=sub['weighted_avg_price'],
        mode='lines+markers', name='Cash',
        line=dict(color=GOLD, width=2.5), marker=dict(size=4),
        connectgaps=False, hovertemplate='Cash: $%{y:.2f}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=sub['doy'], y=sub['close'],
        mode='lines+markers', name='Nearby Futures (LE)',
        line=dict(color=BLUE, width=2.5), marker=dict(size=4),
        connectgaps=False, hovertemplate='Futures: $%{y:.2f}<extra></extra>',
    ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(**MON_TICKS)
    return to_json(fig)


def chart_basis_rolling(cash_df, futures_df, height=290):
    """Weekly basis bars + 4-week rolling average."""
    basis_df = _prep_basis(cash_df, futures_df)
    curr_yr = basis_df['Year'].max()
    sub = _drop_partial(basis_df[basis_df['Year'] == curr_yr].sort_values('week_start').copy(), 'basis')

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sub['doy'], y=sub['basis'],
        marker_color=[GREEN if v >= 0 else RED for v in sub['basis']],
        marker_line_width=0, name='Weekly basis',
        hovertemplate='Basis: $%{y:.2f}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=sub['doy'], y=sub['rolling_basis'],
        mode='lines', name='4-wk avg',
        line=dict(color=GOLD, width=2),
        connectgaps=False, hovertemplate='4-wk: $%{y:.2f}<extra></extra>',
    ))
    fig.add_hline(y=0, line_color='rgba(255,255,255,0.15)', line_width=1)
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(**MON_TICKS)
    return to_json(fig)


def chart_basis_band(cash_df, futures_df, height=310):
    """Current basis vs 5-year historical range band."""
    basis_df = _prep_basis(cash_df, futures_df)
    curr_yr = basis_df['Year'].max()
    fig = go.Figure()
    fig = _band(fig, basis_df, 'basis', curr_yr)
    sub = _drop_partial(basis_df[basis_df['Year'] == curr_yr].sort_values('week_start').copy(), 'basis')
    fig.add_trace(go.Scatter(
        x=sub['doy'], y=sub['basis'],
        mode='lines+markers', name=str(curr_yr),
        line=dict(color=GOLD, width=2.5), marker=dict(size=5, color=GOLD),
        connectgaps=False, hovertemplate='Basis: $%{y:.2f}<extra></extra>',
    ))
    fig.add_hline(y=0, line_color=SUB, line_dash='dot', line_width=1.5,
                  annotation_text='Even', annotation_font_color=SUB, annotation_position='right')
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(**MON_TICKS)
    return to_json(fig)


def chart_basis_by_month(cash_df, futures_df, height=280):
    """Average basis by calendar month — seasonal pattern."""
    basis_df = _prep_basis(cash_df, futures_df)
    basis_df['month'] = pd.to_datetime(basis_df['week_start']).dt.month
    month_names = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',
                   7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
    avg = basis_df.groupby('month')['basis'].mean().reset_index()
    avg['month_name'] = avg['month'].map(month_names)

    fig = go.Figure(go.Bar(
        x=avg['month_name'], y=avg['basis'],
        marker_color=[GREEN if v >= 0 else RED for v in avg['basis']],
        marker_line_width=0,
        hovertemplate='%{x}: $%{y:.2f}<extra></extra>',
    ))
    fig.add_hline(y=0, line_color='rgba(255,255,255,0.2)', line_width=1)
    fig.update_layout(**_L(height=height, yprefix='$'))
    return to_json(fig)


def chart_futures_curve(futures_df, height=290):
    """Live Cattle futures curve — latest date."""
    ep = futures_df.copy()
    ep['trading_day'] = pd.to_datetime(ep['trading_day'], errors='coerce')
    le = ep[ep['commodity'] == 'LE'].copy()
    latest = le['trading_day'].max()
    curve = le[le['trading_day'] == latest].copy()
    month_order = ['G','J','M','Q','V','Z']
    month_names = {'G':'Feb','J':'Apr','M':'Jun','Q':'Aug','V':'Oct','Z':'Dec'}
    curve['m_num'] = curve['month'].apply(lambda m: month_order.index(m) if m in month_order else 99)
    curve = curve.sort_values('m_num')
    curve['label'] = curve['month'].map(month_names).fillna(curve['month']) + ' ' + curve['year'].astype(str)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=curve['label'], y=curve['close'],
        mode='lines+markers',
        line=dict(color=GOLD, width=2.5),
        marker=dict(size=9, color=GOLD, line=dict(color='#111827', width=2)),
        name='Live Cattle Futures',
        hovertemplate='%{x}: $%{y:.2f}/cwt<extra></extra>',
    ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(title_text='Contract Month', color=SUB, title_font=dict(size=10))
    return to_json(fig)


# ══════════════════════════════════════════════════════════════════════════════
# LRP MODULE
# ══════════════════════════════════════════════════════════════════════════════

def chart_lrp_coverage_vs_futures(lrp_df, commodity='LIVE CATTLE', height=310):
    """Coverage price vs futures by endorsement length."""
    df = lrp_df[lrp_df['commodity'] == commodity].dropna(
        subset=['coverage_price', 'futures_price', 'coverage_level_percent']).copy()
    df = df.sort_values('coverage_level_percent')
    colors = [GOLD, BLUE, GREEN, PURPLE, TEAL, ORANGE]

    fig = go.Figure()
    for i, length in enumerate(sorted(df['endorsement_length'].dropna().unique())[:6]):
        sub = df[df['endorsement_length'] == length].sort_values('coverage_level_percent')
        fig.add_trace(go.Scatter(
            x=sub['coverage_level_percent'] * 100,
            y=sub['coverage_price'],
            name=f'{int(length)}-wk',
            mode='lines+markers',
            line=dict(color=colors[i % len(colors)], width=2),
            marker=dict(size=6),
            hovertemplate='Coverage: %{x:.0f}%<br>Floor: $%{y:.2f}/cwt<extra>' + f'{int(length)}-wk</extra>',
        ))
    futures_price = df['futures_price'].median()
    fig.add_hline(y=futures_price, line_dash='dash', line_color=RED, line_width=1.5,
                  annotation_text=f'Futures: ${futures_price:.2f}',
                  annotation_font_color=RED)
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(title_text='Coverage Level %', color=SUB, ticksuffix='%')
    return to_json(fig)


def chart_lrp_premium_curve(lrp_df, commodity='LIVE CATTLE', height=290):
    """Producer premium per head by coverage level."""
    df = lrp_df[lrp_df['commodity'] == commodity].dropna(
        subset=['per_head_premium', 'coverage_level_percent']).copy()
    colors = [GOLD, BLUE, GREEN, PURPLE, TEAL, ORANGE]

    fig = go.Figure()
    for i, length in enumerate(sorted(df['endorsement_length'].dropna().unique())[:6]):
        sub = df[df['endorsement_length'] == length].sort_values('coverage_level_percent')
        fig.add_trace(go.Scatter(
            x=sub['coverage_level_percent'] * 100,
            y=sub['per_head_premium'],
            name=f'{int(length)}-wk',
            mode='lines+markers',
            line=dict(color=colors[i % len(colors)], width=2),
            marker=dict(size=6),
            hovertemplate='Coverage: %{x:.0f}%<br>Premium: $%{y:.2f}/head<extra>' + f'{int(length)}-wk</extra>',
        ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(title_text='Coverage Level %', color=SUB, ticksuffix='%')
    fig.update_yaxes(title_text='$/head (producer cost after subsidy)')
    return to_json(fig)


def chart_lrp_net_floor(lrp_df, commodity='LIVE CATTLE', height=290):
    """Net floor (coverage price - cwt premium) vs futures — grouped by coverage level."""
    df = lrp_df[lrp_df['commodity'] == commodity].dropna(
        subset=['coverage_price', 'futures_price', 'per_cwt_premium', 'coverage_level_percent']).copy()
    grouped = df.groupby('coverage_level_percent').agg(
        coverage_price=('coverage_price', 'median'),
        per_cwt_premium=('per_cwt_premium', 'median'),
        futures_price=('futures_price', 'median'),
    ).reset_index()
    grouped['net_floor'] = grouped['coverage_price'] - grouped['per_cwt_premium']
    grouped['advantage'] = grouped['net_floor'] - grouped['futures_price']
    colors = [GREEN if v >= 0 else RED for v in grouped['advantage']]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=grouped['coverage_level_percent'] * 100,
        y=grouped['advantage'],
        marker_color=colors,
        name='LRP advantage over futures',
        hovertemplate='Coverage: %{x:.0f}%<br>Advantage: $%{y:.2f}/cwt<extra></extra>',
        width=1.5,
    ))
    fig.add_hline(y=0, line_color='rgba(255,255,255,0.25)', line_width=1.5)
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(title_text='Coverage Level %', color=SUB, ticksuffix='%')
    fig.update_yaxes(title_text='LRP floor minus futures ($/cwt)')
    return to_json(fig)


def chart_lrp_subsidy_value(lrp_df, commodity='LIVE CATTLE', height=280):
    """Government subsidy amount vs producer premium — show the deal."""
    df = lrp_df[lrp_df['commodity'] == commodity].dropna(
        subset=['coverage_level_percent', 'per_head_premium', 'subsidy_percent']).copy()
    df['total_premium'] = df['per_head_premium'] / (1 - df['subsidy_percent'])
    df['govt_share'] = df['total_premium'] - df['per_head_premium']
    grouped = df.groupby('coverage_level_percent').agg(
        producer=('per_head_premium', 'median'),
        govt=('govt_share', 'median'),
    ).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=grouped['coverage_level_percent'] * 100,
        y=grouped['producer'],
        name='Producer pays', marker_color=GOLD, marker_line_width=0,
        hovertemplate='Coverage: %{x:.0f}%<br>Producer: $%{y:.2f}/head<extra></extra>',
    ))
    fig.add_trace(go.Bar(
        x=grouped['coverage_level_percent'] * 100,
        y=grouped['govt'],
        name='USDA subsidy', marker_color=GREEN, marker_line_width=0,
        hovertemplate='Coverage: %{x:.0f}%<br>USDA: $%{y:.2f}/head<extra></extra>',
    ))
    fig.update_layout(**_L(height=height, yprefix='$', barmode='stack'))
    fig.update_xaxes(title_text='Coverage Level %', color=SUB, ticksuffix='%')
    fig.update_yaxes(title_text='$/head total premium')
    return to_json(fig)


# ══════════════════════════════════════════════════════════════════════════════
# WASDE MODULE
# ══════════════════════════════════════════════════════════════════════════════

def chart_wasde_production(wasde_df, commodity='Beef', height=310):
    """Production forecast revisions across report dates by market year."""
    df = wasde_df.copy()
    df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')
    filtered = df[(df['commodity'] == commodity) & (df['attribute'] == 'Production')].dropna(subset=['value'])
    colors = [GOLD, BLUE, GREEN, PURPLE]

    fig = go.Figure()
    for i, (my, grp) in enumerate(filtered.groupby('market_year')):
        grp = grp.sort_values('report_date')
        fig.add_trace(go.Scatter(
            x=grp['report_date'], y=grp['value'],
            name=f'MY {my}',
            mode='lines+markers',
            line=dict(color=colors[i % len(colors)], width=2),
            marker=dict(size=8),
            hovertemplate='%{x|%b %Y}<br>%{y:,.0f} mil lbs<extra>MY ' + str(my) + '</extra>',
        ))
    fig.update_layout(**_L(height=height))
    fig.update_xaxes(title_text='WASDE Report Date', color=SUB)
    fig.update_yaxes(tickformat=',.0f', title_text='Million Lbs')
    return to_json(fig)


def chart_wasde_revisions(wasde_df, height=310):
    """Largest month-over-month WASDE revisions."""
    df = wasde_df.copy()
    df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')
    df = df.sort_values(['commodity', 'attribute', 'market_year', 'report_date'])
    df['prev_value'] = df.groupby(['commodity', 'attribute', 'market_year'])['value'].shift(1)
    df['delta'] = df['value'] - df['prev_value']
    df = df.dropna(subset=['delta'])
    df['abs_delta'] = df['delta'].abs()
    top = df.sort_values('abs_delta', ascending=False).drop_duplicates(
        subset=['commodity', 'attribute']
    ).head(12).sort_values('delta')
    colors = [GREEN if v > 0 else RED for v in top['delta']]
    labels = top['commodity'] + ' — ' + top['attribute']

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=top['delta'], y=labels,
        orientation='h', marker_color=colors, marker_line_width=0,
        name='Revision',
        hovertemplate='%{y}<br>Change: %{x:,.1f}<extra></extra>',
    ))
    fig.add_vline(x=0, line_color='rgba(255,255,255,0.2)', line_width=1)
    fig.update_layout(**_L(height=height, margin=dict(l=200, r=8, t=12, b=8)))
    fig.update_xaxes(title_text='Change vs. Prior Report', color=SUB)
    fig.update_yaxes(tickfont=dict(color=SUB, size=10))
    return to_json(fig)


def chart_wasde_price_forecasts(wasde_df, height=290):
    """Steer and Barrow/gilt price forecasts across WASDE dates."""
    df = wasde_df.copy()
    df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')
    prices = df[
        (df['commodity'].isin(['Steers', 'Barrows and gilts'])) &
        (df['attribute'] == 'Prices')
    ].dropna(subset=['value'])
    color_map = {'Steers': GOLD, 'Barrows and gilts': BLUE}

    fig = go.Figure()
    for commodity, grp in prices.groupby('commodity'):
        grp = grp.sort_values('report_date')
        fig.add_trace(go.Scatter(
            x=grp['report_date'], y=grp['value'],
            name=commodity,
            mode='lines+markers',
            line=dict(color=color_map.get(commodity, GREEN), width=2.5),
            marker=dict(size=8),
            hovertemplate='%{x|%b %Y}<br>$%{y:.2f}<extra>' + commodity + '</extra>',
        ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(title_text='WASDE Report Date', color=SUB)
    return to_json(fig)


def chart_wasde_supply_demand(wasde_df, commodity='Beef', height=290):
    """Supply vs demand attributes across WASDE dates."""
    df = wasde_df.copy()
    df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')
    filtered = df[df['commodity'] == commodity].dropna(subset=['value'])
    supply_attrs = filtered[filtered['attribute'].str.contains('Production|Total Supply', na=False)]
    demand_attrs = filtered[filtered['attribute'].str.contains('Total Use|Exports|Per Capita', na=False)]

    fig = go.Figure()
    supply_colors = [GOLD, ORANGE]
    demand_colors = [BLUE, TEAL, PURPLE]
    for i, (attr, grp) in enumerate(supply_attrs.groupby('attribute')):
        grp = grp.sort_values('report_date')
        fig.add_trace(go.Scatter(
            x=grp['report_date'], y=grp['value'],
            name=attr, mode='lines+markers',
            line=dict(color=supply_colors[i % len(supply_colors)], width=2),
            marker=dict(size=6),
            hovertemplate=f'{attr}: %{{y:,.0f}}<extra></extra>',
        ))
    for i, (attr, grp) in enumerate(demand_attrs.groupby('attribute')):
        grp = grp.sort_values('report_date')
        fig.add_trace(go.Scatter(
            x=grp['report_date'], y=grp['value'],
            name=attr, mode='lines+markers',
            line=dict(color=demand_colors[i % len(demand_colors)], width=1.5, dash='dot'),
            marker=dict(size=6),
            hovertemplate=f'{attr}: %{{y:,.0f}}<extra></extra>',
        ))
    fig.update_layout(**_L(height=height))
    fig.update_xaxes(title_text='WASDE Report Date', color=SUB)
    fig.update_yaxes(tickformat=',.0f', title_text='Million Lbs')
    return to_json(fig)


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD CHARTS
# ══════════════════════════════════════════════════════════════════════════════

def chart_dashboard_slaughter_sparkline(df, height=220):
    """Cattle vs Hog slaughter — last 12 weeks sparkline."""
    df = df.copy()
    df['slaughter_date'] = pd.to_datetime(df['slaughter_date'], errors='coerce')
    df = df[df['period'] == 'Current'].dropna(subset=['slaughter_date', 'slaughter'])
    df['week_start'] = df['slaughter_date'] - pd.to_timedelta(df['slaughter_date'].dt.weekday, unit='D')

    fig = go.Figure()
    for commodity, color in [('Cattle', GOLD), ('Hogs', BLUE)]:
        sub = df[df['commodity'] == commodity].groupby('week_start')['slaughter'].sum().reset_index()
        sub = sub.sort_values('week_start').tail(12)
        sub = _drop_partial(sub, 'slaughter')
        # WoW % change
        sub['wow'] = sub['slaughter'].pct_change() * 100
        fig.add_trace(go.Scatter(
            x=sub['week_start'], y=sub['slaughter'],
            mode='lines+markers', name=commodity,
            line=dict(color=color, width=2),
            marker=dict(size=5),
            connectgaps=False,
            hovertemplate=f'{commodity}: %{{y:,.0f}} head<extra></extra>',
        ))
    fig.update_layout(**_L(height=height))
    fig.update_xaxes(title_text='', tickformat='%b %d')
    fig.update_yaxes(tickformat=',.0f', title_text='Head')
    return to_json(fig)


def chart_dashboard_species_mix(df, height=220):
    """Pie chart — cattle vs hog % of total weekly slaughter."""
    df = df.copy()
    df['slaughter_date'] = pd.to_datetime(df['slaughter_date'], errors='coerce')
    df = df[df['period'] == 'Current'].dropna(subset=['slaughter_date', 'slaughter'])
    df['week_start'] = df['slaughter_date'] - pd.to_timedelta(df['slaughter_date'].dt.weekday, unit='D')
    latest_week = df['week_start'].max()
    week_data = df[df['week_start'] == latest_week].groupby('commodity')['slaughter'].sum()
    week_data = week_data[week_data.index.isin(['Cattle', 'Hogs'])]

    fig = go.Figure(go.Pie(
        labels=week_data.index.tolist(),
        values=week_data.values.tolist(),
        hole=0.55,
        marker=dict(colors=[GOLD, BLUE]),
        textfont=dict(size=12, color='#1A1D2E'),
        hovertemplate='%{label}: %{value:,.0f} head (%{percent})<extra></extra>',
    ))
    fig.update_layout(
        **_L(height=height),
        annotations=[dict(text='This<br>Week', x=0.5, y=0.5, font_size=11,
                          showarrow=False, font_color='#5A6077')],
        showlegend=True,
    )
    return to_json(fig)


def chart_dashboard_cow_donut(cow_df, height=220):
    """Donut — dairy vs other cow slaughter latest week."""
    cow_df = cow_df.copy()
    cow_df['report_date'] = pd.to_datetime(cow_df['report_date'], errors='coerce')
    cow_df = cow_df[cow_df['class_name'].isin(['Dairy Cows', 'Other Cows'])].dropna(subset=['volume'])
    cow_df = cow_df[cow_df['volume'] > 1000]
    latest = cow_df['report_date'].max()
    week_data = cow_df[cow_df['report_date'] == latest].groupby('class_name')['volume'].sum()

    fig = go.Figure(go.Pie(
        labels=week_data.index.tolist(),
        values=week_data.values.tolist(),
        hole=0.55,
        marker=dict(colors=[BLUE, ORANGE]),
        textfont=dict(size=12, color='#1A1D2E'),
        hovertemplate='%{label}: %{value:,.0f}<extra></extra>',
    ))
    fig.update_layout(
        **_L(height=height),
        annotations=[dict(text='Cow<br>Mix', x=0.5, y=0.5, font_size=11,
                          showarrow=False, font_color='#5A6077')],
        showlegend=True,
    )
    return to_json(fig)


def chart_dashboard_cutout_sparkline(cutout_df, height=220):
    """Choice vs Select cutout last 8 weeks sparkline."""
    cutout_df = cutout_df.copy()
    cutout_df['report_date'] = pd.to_datetime(cutout_df['report_date'], errors='coerce')
    cutout_df = cutout_df.sort_values('report_date')

    fig = go.Figure()
    for attr, color in [('Choice', GOLD), ('Select', BLUE)]:
        sub = cutout_df[cutout_df['attribute'] == attr].tail(40)
        fig.add_trace(go.Scatter(
            x=sub['report_date'], y=sub['value'],
            mode='lines+markers', name=attr,
            line=dict(color=color, width=2),
            marker=dict(size=4),
            connectgaps=False,
            hovertemplate=f'{attr}: $%{{y:.2f}}<extra></extra>',
        ))
    fig.update_layout(**_L(height=height))
    fig.update_xaxes(tickformat='%b %d')
    fig.update_yaxes(tickprefix='$', title_text='$/cwt')
    return to_json(fig)


def chart_dashboard_primal_heatmap(primal_df, height=220):
    """Primal values bar — which cuts are hot vs cold this week."""
    primal_df = primal_df.copy()
    primal_df['report_date'] = pd.to_datetime(primal_df['report_date'], errors='coerce')
    latest = primal_df['report_date'].max()
    curr = primal_df[primal_df['report_date'] == latest].dropna(subset=['choice_600_900'])
    prev_date = primal_df[primal_df['report_date'] < latest]['report_date'].max()
    prev = primal_df[primal_df['report_date'] == prev_date].dropna(subset=['choice_600_900'])

    merged = curr.merge(prev[['primal_desc', 'choice_600_900']], on='primal_desc', suffixes=('', '_prev'))
    merged['pct_change'] = (merged['choice_600_900'] - merged['choice_600_900_prev']) / merged['choice_600_900_prev'] * 100
    merged = merged.sort_values('pct_change', ascending=True)

    colors = [GREEN if v >= 0 else RED for v in merged['pct_change']]
    fig = go.Figure(go.Bar(
        y=merged['primal_desc'], x=merged['pct_change'],
        orientation='h',
        marker_color=colors,
        marker_line_width=0,
        hovertemplate='%{y}: %{x:+.1f}%<extra></extra>',
    ))
    fig.add_vline(x=0, line_color='#9BA3B8', line_width=1)
    fig.update_layout(**_L(height=height, margin=dict(l=80, r=10, t=14, b=10)))
    fig.update_xaxes(ticksuffix='%', title_text='WoW % Change')
    return to_json(fig)


def chart_dashboard_cutout_vs_avg(cutout_df, height=220):
    """Donut — is current Choice cutout above or below 5-year average."""
    cutout_df = cutout_df.copy()
    cutout_df['report_date'] = pd.to_datetime(cutout_df['report_date'], errors='coerce')
    choice = cutout_df[cutout_df['attribute'] == 'Choice'].copy()
    choice['week_of_year'] = choice['report_date'].dt.isocalendar().week
    latest = choice.sort_values('report_date').iloc[-1]
    curr_val = latest['value']
    curr_wk = latest['week_of_year']
    hist_avg = choice[
        (choice['week_of_year'] == curr_wk) &
        (choice['report_date'] < latest['report_date'])
    ]['value'].mean()

    if pd.isna(hist_avg):
        hist_avg = curr_val

    pct_above = ((curr_val - hist_avg) / hist_avg * 100)
    label = f"{'Above' if pct_above >= 0 else 'Below'} avg<br>{abs(pct_above):.1f}%"
    color = GREEN if pct_above >= 0 else RED

    fig = go.Figure(go.Pie(
        labels=['Current', 'Historical Avg'],
        values=[curr_val, hist_avg],
        hole=0.6,
        marker=dict(colors=[color, '#E2E6EE']),
        textinfo='none',
        hovertemplate='%{label}: $%{value:.2f}<extra></extra>',
        showlegend=False,
    ))
    fig.update_layout(
        **_L(height=height),
        annotations=[dict(text=label, x=0.5, y=0.5, font_size=11,
                          showarrow=False, font_color='#1A1D2E', align='center')],
    )
    return to_json(fig)


def chart_dashboard_cash_futures_sparkline(cash_df, futures_df, height=220):
    """Cash vs futures last 8 weeks."""
    cash_df = cash_df.copy()
    futures_df = futures_df.copy()
    cash_df['report_date'] = pd.to_datetime(cash_df['report_date'], errors='coerce')
    futures_df['trading_day'] = pd.to_datetime(futures_df['trading_day'], errors='coerce')

    cash = cash_df[(cash_df['class_description'] == 'ALL BEEF TYPE') &
                   (cash_df['selling_basis'] == 'LIVE DELIVERED')].copy()
    cash_w = cash.groupby(cash['report_date'].dt.to_period('W').apply(lambda r: r.start_time))['weighted_avg_price'].mean().reset_index()
    cash_w.columns = ['date', 'cash']
    cash_w = cash_w.tail(10)

    le = futures_df[futures_df['commodity'] == 'LE'].copy()
    fut_w = le.groupby(le['trading_day'].dt.to_period('W').apply(lambda r: r.start_time))['close'].mean().reset_index()
    fut_w.columns = ['date', 'futures']
    fut_w = fut_w.tail(10)

    merged = pd.merge(cash_w, fut_w, on='date', how='inner').sort_values('date')

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=merged['date'], y=merged['cash'],
        mode='lines+markers', name='Cash',
        line=dict(color=GOLD, width=2), marker=dict(size=5),
        hovertemplate='Cash: $%{y:.2f}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=merged['date'], y=merged['futures'],
        mode='lines+markers', name='Futures',
        line=dict(color=BLUE, width=2, dash='dash'), marker=dict(size=5),
        hovertemplate='Futures: $%{y:.2f}<extra></extra>',
    ))
    fig.update_layout(**_L(height=height))
    fig.update_xaxes(tickformat='%b %d')
    fig.update_yaxes(tickprefix='$')
    return to_json(fig)


def chart_dashboard_basis_gauge(cash_df, futures_df, height=220):
    """Gauge chart — is basis wide, tight, or normal."""
    try:
        cash_df = cash_df.copy()
        futures_df = futures_df.copy()
        cash_df['report_date'] = pd.to_datetime(cash_df['report_date'], errors='coerce')
        futures_df['trading_day'] = pd.to_datetime(futures_df['trading_day'], errors='coerce')

        cash = cash_df[(cash_df['class_description'] == 'ALL BEEF TYPE') &
                       (cash_df['selling_basis'] == 'LIVE DELIVERED')].copy()
        latest_cash = cash.sort_values('report_date').tail(5)['weighted_avg_price'].mean()
        le = futures_df[futures_df['commodity'] == 'LE'].copy()
        le = le.sort_values('trading_day')
        nearby = le.groupby('trading_day').first().reset_index()
        latest_futures = nearby.tail(5)['close'].mean()
        current_basis = latest_cash - latest_futures

        # Historical basis range
        cash_w = cash.groupby(cash['report_date'].dt.to_period('W').apply(lambda r: r.start_time))['weighted_avg_price'].mean().reset_index()
        cash_w.columns = ['date', 'cash']
        fut_w = nearby.groupby(nearby['trading_day'].dt.to_period('W').apply(lambda r: r.start_time))['close'].mean().reset_index()
        fut_w.columns = ['date', 'futures']
        merged = pd.merge(cash_w, fut_w, on='date', how='inner')
        merged['basis'] = merged['cash'] - merged['futures']
        basis_min = merged['basis'].quantile(0.1)
        basis_max = merged['basis'].quantile(0.9)
        basis_mid = merged['basis'].median()

        fig = go.Figure(go.Indicator(
            mode='gauge+number+delta',
            value=round(current_basis, 2),
            delta={'reference': round(basis_mid, 2), 'valueformat': '.2f'},
            title={'text': 'Current Basis ($/cwt)', 'font': {'size': 12, 'color': '#5A6077'}},
            number={'prefix': '$', 'valueformat': '.2f', 'font': {'color': '#1A1D2E', 'size': 20}},
            gauge={
                'axis': {'range': [basis_min, basis_max], 'tickprefix': '$',
                         'tickfont': {'color': '#5A6077', 'size': 10}},
                'bar': {'color': GOLD},
                'bgcolor': '#F7F8FA',
                'bordercolor': '#E2E6EE',
                'steps': [
                    {'range': [basis_min, basis_mid * 0.8], 'color': '#FDECEA'},
                    {'range': [basis_mid * 0.8, basis_mid * 1.2], 'color': '#F0F7F0'},
                    {'range': [basis_mid * 1.2, basis_max], 'color': '#E8F4ED'},
                ],
                'threshold': {
                    'line': {'color': '#1A6E3C', 'width': 2},
                    'thickness': 0.75,
                    'value': round(basis_mid, 2),
                },
            },
        ))
        fig.update_layout(**_L(height=height, margin=dict(l=20, r=20, t=40, b=10)))
        return to_json(fig)
    except Exception as e:
        return to_json(go.Figure().update_layout(**_L(height=height,
            title=f'Basis gauge unavailable: {str(e)}')))


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD V2 CHARTS
# ══════════════════════════════════════════════════════════════════════════════

def _agg_slaughter(df, period='week'):
    """Aggregate slaughter data by period."""
    df = df.copy()
    df['slaughter_date'] = pd.to_datetime(df['slaughter_date'], errors='coerce')
    df['monday'] = pd.to_datetime(df['monday_of_week'], errors='coerce')
    df = df.dropna(subset=['slaughter_date', 'slaughter'])

    if period == 'week':
        grp = df.groupby('monday').agg(
            slaughter=('week_to_date', 'max'),
            year_ago=('year_ago', 'sum'),
        ).reset_index().rename(columns={'monday': 'date'})
        grp = _drop_partial(grp, 'slaughter')
        tick_fmt = '%b %d'
    elif period == 'month':
        df['month'] = df['slaughter_date'].dt.to_period('M').apply(lambda r: r.start_time)
        grp = df.groupby('month').agg(
            slaughter=('slaughter', 'sum'),
            year_ago=('year_ago', 'sum'),
        ).reset_index().rename(columns={'month': 'date'})
        tick_fmt = '%b %Y'
    else:  # year
        df['year_dt'] = pd.to_datetime(df['slaughter_date'].dt.year.astype(str) + '-01-01')
        grp = df.groupby('year_dt').agg(
            slaughter=('slaughter', 'sum'),
            year_ago=('year_ago', 'sum'),
        ).reset_index().rename(columns={'year_dt': 'date'})
        tick_fmt = '%Y'

    grp = grp.sort_values('date')
    return grp, tick_fmt


def chart_dash_slaughter(df, commodity='Cattle', period='week', height=260):
    """Dashboard slaughter chart with period toggle support."""
    grp, tick_fmt = _agg_slaughter(df, period)
    color = GOLD if commodity == 'Cattle' else BLUE

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=grp['date'], y=grp['slaughter'],
        mode='lines+markers', name='This Period',
        line=dict(color=color, width=2.5),
        marker=dict(size=5),
        connectgaps=False,
        hovertemplate='%{x}<br>%{y:,.0f} head<extra>This Period</extra>',
    ))
    if grp['year_ago'].notna().any():
        fig.add_trace(go.Scatter(
            x=grp['date'], y=grp['year_ago'],
            mode='lines', name='Year Ago',
            line=dict(color=MUTED, width=1.5, dash='dash'),
            connectgaps=False,
            hovertemplate='%{y:,.0f} head<extra>Year Ago</extra>',
        ))
    fig.update_layout(**_L(height=height))
    fig.update_xaxes(tickformat=tick_fmt, tickfont=dict(color=SUB, size=10))
    fig.update_yaxes(tickformat=',.0f', title_text='Head')
    return to_json(fig)


def chart_dash_cattle_cash(df, height=260):
    """Cash cattle price trend."""
    df = df.copy()
    df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')
    df = df.sort_values('report_date').tail(260)  # last ~year

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['report_date'], y=df['weighted_avg_price'],
        mode='lines', name='Cash Price',
        line=dict(color=GOLD, width=2.5),
        fill='tozeroy', fillcolor='rgba(184,115,10,0.06)',
        connectgaps=False,
        hovertemplate='%{x|%b %d}<br>$%{y:.2f}/cwt<extra>Cash</extra>',
    ))
    # Rolling 4-week avg
    df['roll'] = df['weighted_avg_price'].rolling(20, min_periods=1).mean()
    fig.add_trace(go.Scatter(
        x=df['report_date'], y=df['roll'],
        mode='lines', name='4-wk avg',
        line=dict(color=TEAL, width=1.5, dash='dot'),
        connectgaps=False,
        hovertemplate='$%{y:.2f}<extra>4-wk avg</extra>',
    ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(tickformat='%b %y', tickfont=dict(color=SUB, size=10))
    return to_json(fig)


def chart_dash_beef_cutout(df, height=260):
    """Choice cutout value trend."""
    df = df.copy()
    df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')
    choice = df[df['attribute'] == 'Choice'].sort_values('report_date').tail(365)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=choice['report_date'], y=choice['value'],
        mode='lines', name='Choice Cutout',
        line=dict(color=GOLD, width=2.5),
        fill='tozeroy', fillcolor='rgba(184,115,10,0.06)',
        connectgaps=False,
        hovertemplate='%{x|%b %d}<br>$%{y:.2f}/cwt<extra>Choice</extra>',
    ))
    choice['roll'] = choice['value'].rolling(5, min_periods=1).mean()
    fig.add_trace(go.Scatter(
        x=choice['report_date'], y=choice['roll'],
        mode='lines', name='5-day avg',
        line=dict(color=TEAL, width=1.5, dash='dot'),
        connectgaps=False,
        hovertemplate='$%{y:.2f}<extra>5-day avg</extra>',
    ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(tickformat='%b %y', tickfont=dict(color=SUB, size=10))
    return to_json(fig)


def chart_dash_pork_regional(df, height=260):
    """National, Iowa/SMN and Western Cornbelt hog prices on one chart."""
    df = df.copy()
    df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')
    df = df.sort_values('report_date')

    color_map = {'National': GOLD, 'IASWMN': BLUE, 'Western Cornbelt': GREEN}
    fig = go.Figure()
    label_map = {'National': 'National', 'IASWMN': 'Iowa/S.MN', 'Western Cornbelt': 'W. Cornbelt'}
    for region, color in color_map.items():
        sub = df[df['name'] == region].tail(365)
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub['report_date'], y=sub['wtd_avg'],
            mode='lines',
            name=label_map.get(region, region),
            line=dict(color=color, width=2),
            connectgaps=False,
            hovertemplate=f'{label_map.get(region, region)}: $%{{y:.2f}}<extra></extra>',
        ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(tickformat='%b %y', tickfont=dict(color=SUB, size=10))
    return to_json(fig)


def chart_dash_pork_cutout(df, height=260):
    """Pork carcass value trend."""
    df = df.copy()
    df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')
    carcass = df[df['commodity'] == 'Carcass'].sort_values('report_date').tail(365)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=carcass['report_date'], y=carcass['value'],
        mode='lines', name='Pork Carcass Value',
        line=dict(color=BLUE, width=2.5),
        fill='tozeroy', fillcolor='rgba(26,92,158,0.06)',
        connectgaps=False,
        hovertemplate='%{x|%b %d}<br>$%{y:.2f}/cwt<extra>Pork Carcass</extra>',
    ))
    carcass['roll'] = carcass['value'].rolling(5, min_periods=1).mean()
    fig.add_trace(go.Scatter(
        x=carcass['report_date'], y=carcass['roll'],
        mode='lines', name='5-day avg',
        line=dict(color=TEAL, width=1.5, dash='dot'),
        connectgaps=False,
        hovertemplate='$%{y:.2f}<extra>5-day avg</extra>',
    ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(tickformat='%b %y', tickfont=dict(color=SUB, size=10))
    return to_json(fig)


def chart_dash_feed_futures(df, commodity='corn', height=240):
    """Corn or soy futures — all contracts on one chart."""
    df = df.copy()
    df['trade_date'] = pd.to_datetime(df['trade_date'], errors='coerce')
    sub = df[df['commodity'] == commodity].sort_values('trade_date')
    color = GOLD if commodity == 'corn' else GREEN
    colors_list = [color, BLUE, PURPLE, ORANGE, TEAL, RED]

    fig = go.Figure()
    for i, (symbol, grp) in enumerate(sub.groupby('symbol')):
        contract = grp['contract_month'].iloc[0]
        grp = grp.sort_values('trade_date')
        fig.add_trace(go.Scatter(
            x=grp['trade_date'], y=grp['close_price'],
            mode='lines', name=f'{symbol} ({contract})',
            line=dict(color=colors_list[i % len(colors_list)], width=1.8),
            connectgaps=False,
            hovertemplate=f'{symbol}: $%{{y:.4f}}<extra></extra>',
        ))
    label = 'Corn' if commodity == 'corn' else 'Soybeans'
    fig.update_layout(**_L(height=height))
    fig.update_xaxes(tickformat='%b %y', tickfont=dict(color=SUB, size=10))
    fig.update_yaxes(tickprefix='$', title_text=f'{label} ($/bu)')
    return to_json(fig)


# ══════════════════════════════════════════════════════════════════════════════
# HOG-SPECIFIC CHARTS
# ══════════════════════════════════════════════════════════════════════════════

def chart_hog_slaughter_seasonal(slaughter_df, height=380):
    """Hog slaughter this year vs year ago — grouped bar, same style as cattle."""
    return chart_slaughter_seasonal(slaughter_df, 'Hogs', BLUE, height=height)


def chart_hog_carcass_weights(harvest_usda_df, height=340):
    """Avg hog carcass weight vs 5-year seasonal band."""
    df = harvest_usda_df.copy()
    df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')
    df = df.dropna(subset=['report_date', 'avg_carcass_weight'])
    df = df.sort_values('report_date')

    current_year = df['report_date'].dt.year.max()
    curr = df[df['report_date'].dt.year == current_year].copy()
    hist = df[df['report_date'].dt.year < current_year].copy()

    # 5-year band by week of year
    hist['week_of_year'] = hist['report_date'].dt.isocalendar().week.astype(int)
    band = hist.groupby('week_of_year')['avg_carcass_weight'].agg(
        low=lambda x: x.quantile(0.10),
        high=lambda x: x.quantile(0.90),
        avg='mean',
    ).reset_index()

    curr['week_of_year'] = curr['report_date'].dt.isocalendar().week.astype(int)
    curr_band = curr.merge(band, on='week_of_year', how='left')
    curr_band = _drop_partial(curr_band, 'avg_carcass_weight')

    fig = go.Figure()
    # Band
    fig.add_trace(go.Scatter(
        x=curr_band['report_date'].tolist() + curr_band['report_date'].tolist()[::-1],
        y=curr_band['high'].tolist() + curr_band['low'].tolist()[::-1],
        fill='toself', fillcolor=BAND, line=dict(width=0),
        name='5-yr Range', hoverinfo='skip', showlegend=True,
    ))
    # 5yr avg
    fig.add_trace(go.Scatter(
        x=curr_band['report_date'], y=curr_band['avg'],
        mode='lines', name='5-yr Avg',
        line=dict(color=MUTED, width=1.2, dash='dot'),
        connectgaps=False,
    ))
    # This year
    fig.add_trace(go.Scatter(
        x=curr_band['report_date'], y=curr_band['avg_carcass_weight'],
        mode='lines+markers', name=str(current_year),
        line=dict(color=BLUE, width=2.5),
        marker=dict(size=4),
        connectgaps=False,
        hovertemplate='%{x|%b %d}: %{y:.1f} lbs<extra></extra>',
    ))
    fig.update_layout(**_L(height=height))
    fig.update_xaxes(tickformat="%b '%y")
    fig.update_yaxes(ticksuffix=' lbs', title_text='Avg Carcass Weight')
    return to_json(fig)


def chart_implied_pork_production(slaughter_df, harvest_usda_df, height=320):
    """Implied pork production = hog head count x avg carcass weight."""
    sl = slaughter_df.copy()
    sl['slaughter_date'] = pd.to_datetime(sl['slaughter_date'], errors='coerce')
    sl = sl[sl['commodity'].isin(['Hogs', 'Slaughter Hogs']) & (sl['period'] == 'Current')]
    sl['week'] = sl['slaughter_date'].dt.to_period('W').apply(lambda r: r.start_time)
    sl_w = sl.groupby('week')['slaughter'].sum().reset_index()

    hu = harvest_usda_df.copy()
    hu['report_date'] = pd.to_datetime(hu['report_date'], errors='coerce')
    hu['week'] = hu['report_date'].dt.to_period('W').apply(lambda r: r.start_time)
    hu_w = hu.groupby('week')['avg_carcass_weight'].mean().reset_index()

    merged = pd.merge(sl_w, hu_w, on='week', how='inner')
    merged['implied_lbs'] = merged['slaughter'] * merged['avg_carcass_weight']
    merged = merged.sort_values('week')
    merged = _drop_partial(merged, 'implied_lbs')

    # Rolling 4-week avg
    merged['roll'] = merged['implied_lbs'].rolling(4, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=merged['week'], y=merged['implied_lbs'],
        name='Weekly Production',
        marker_color=BLUE, marker_line_width=0,
        hovertemplate='%{x|%b %d}: %{y:,.0f} lbs<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=merged['week'], y=merged['roll'],
        mode='lines', name='4-wk Avg',
        line=dict(color=GOLD, width=2),
        connectgaps=False,
        hovertemplate='%{y:,.0f} lbs<extra>4-wk avg</extra>',
    ))
    fig.update_layout(**_L(height=height))
    fig.update_xaxes(tickformat="%b '%y")
    fig.update_yaxes(tickformat=',.0f', title_text='Lbs')
    return to_json(fig)


def chart_hog_class_breakdown(slaughter_df, sow_df, height=310):
    """Sows vs market hogs (Barrows & Gilts) slaughter — breeding herd signal."""
    # Get total hog slaughter
    sl = slaughter_df.copy()
    sl['slaughter_date'] = pd.to_datetime(sl['slaughter_date'], errors='coerce')
    sl = sl[sl['commodity'].isin(['Hogs', 'Slaughter Hogs']) & (sl['period'] == 'Current')]
    sl['week'] = sl['slaughter_date'].dt.to_period('W').apply(lambda r: r.start_time)
    total = sl.groupby('week')['slaughter'].sum().reset_index()
    total.columns = ['week', 'total']

    # Get sow slaughter
    sw = sow_df.copy()
    sw['report_date'] = pd.to_datetime(sw['report_date'], errors='coerce')
    sw['week'] = sw['report_date'].dt.to_period('W').apply(lambda r: r.start_time)
    sows = sw.groupby('week')['volume'].sum().reset_index()
    sows.columns = ['week', 'sows']

    # Merge and compute market hogs
    merged = pd.merge(total, sows, on='week', how='inner')
    merged['market_hogs'] = merged['total'] - merged['sows']
    merged['week_dt'] = merged['week'].apply(lambda w: w.start_time if hasattr(w, 'start_time') else pd.Timestamp(str(w)))
    merged = merged.sort_values('week_dt')
    merged = merged[merged['market_hogs'] > 0]

    curr_year = merged['week_dt'].dt.year.max()
    curr = merged[merged['week_dt'].dt.year == curr_year].copy()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=curr['week_dt'], y=curr['market_hogs'],
        mode='lines+markers', name='Barrows & Gilts (Market)',
        line=dict(color=BLUE, width=2.5),
        marker=dict(size=4),
        connectgaps=False,
        hovertemplate='%{x|%b %d}<br>%{y:,.0f} head<extra>Market Hogs</extra>',
    ))
    fig.add_trace(go.Scatter(
        x=curr['week_dt'], y=curr['sows'],
        mode='lines+markers', name='Sows (Breeding)',
        line=dict(color=ORANGE, width=2.5),
        marker=dict(size=4),
        connectgaps=False,
        hovertemplate='%{x|%b %d}<br>%{y:,.0f} head<extra>Sows</extra>',
    ))
    fig.update_layout(**_L(height=height))
    fig.update_xaxes(tickformat="%b '%y")
    fig.update_yaxes(tickformat=',.0f', title_text='Head')
    return to_json(fig)


# ══════════════════════════════════════════════════════════════════════════════
# CUTOUT MODULE — PORK CHARTS
# ══════════════════════════════════════════════════════════════════════════════

def chart_pork_belly_vs_carcass(pork_df, height=310):
    """Pork belly vs carcass value — current year."""
    pork_df = pork_df.copy()
    pork_df['report_date'] = pd.to_datetime(pork_df['report_date'], errors='coerce')
    pork_df['week_start'] = pork_df['report_date'] - pd.to_timedelta(pork_df['report_date'].dt.weekday, unit='D')
    pork_df['Year'] = pork_df['week_start'].dt.year
    curr_yr = pork_df['Year'].max()

    fig = go.Figure()
    for cut, color in [('Belly', GOLD), ('Carcass', BLUE)]:
        sub = pork_df[(pork_df['commodity'] == cut) & (pork_df['Year'] == curr_yr)]
        sub = sub.groupby('week_start')['value'].mean().reset_index().sort_values('week_start')
        sub = _drop_partial(sub, 'value')
        sub['doy'] = sub['week_start'].dt.dayofyear
        fig.add_trace(go.Scatter(
            x=sub['doy'], y=sub['value'],
            mode='lines+markers', name=cut,
            line=dict(color=color, width=2.5), marker=dict(size=4),
            connectgaps=False,
            hovertemplate=f'{cut}: $%{{y:.2f}}<extra></extra>',
        ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(**MON_TICKS)
    return to_json(fig)


def chart_pork_seasonal_cutout(pork_df, height=310):
    """Seasonal pork cutout pattern — belly and carcass historical average."""
    pork_df = pork_df.copy()
    pork_df['report_date'] = pd.to_datetime(pork_df['report_date'], errors='coerce')
    pork_df['week_start'] = pork_df['report_date'] - pd.to_timedelta(pork_df['report_date'].dt.weekday, unit='D')
    pork_df['Year'] = pork_df['week_start'].dt.year
    pork_df['iso_week'] = pork_df['week_start'].apply(lambda x: x.isocalendar().week)
    curr_yr = pork_df['Year'].max()

    fig = go.Figure()
    for cut, color in [('Belly', GOLD), ('Carcass', BLUE)]:
        sub = pork_df[pork_df['commodity'] == cut].copy()
        curr = sub[sub['Year'] == curr_yr].groupby('iso_week')['value'].mean().reset_index()
        hist_avg = sub[sub['Year'] < curr_yr].groupby('iso_week')['value'].mean().reset_index()
        fig.add_trace(go.Scatter(
            x=curr['iso_week'], y=curr['value'],
            mode='lines+markers', name=f'{cut} {curr_yr}',
            line=dict(color=color, width=2.5), marker=dict(size=4),
            connectgaps=False,
            hovertemplate=f'{cut}: $%{{y:.2f}}<extra></extra>',
        ))
        fig.add_trace(go.Scatter(
            x=hist_avg['iso_week'], y=hist_avg['value'],
            mode='lines', name=f'{cut} hist avg',
            line=dict(color=color, width=1.2, dash='dot'),
            connectgaps=False,
            hovertemplate=f'{cut} avg: $%{{y:.2f}}<extra></extra>',
        ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(title_text='Week of Year', tickfont=dict(color=SUB, size=10))
    return to_json(fig)


def chart_pork_yoy_pct(pork_df, cut='Carcass', height=280):
    """Pork cut % change vs year ago."""
    pork_df = pork_df.copy()
    pork_df['report_date'] = pd.to_datetime(pork_df['report_date'], errors='coerce')
    pork_df['week_start'] = pork_df['report_date'] - pd.to_timedelta(pork_df['report_date'].dt.weekday, unit='D')
    pork_df['Year'] = pork_df['week_start'].dt.year
    pork_df['iso_week'] = pork_df['week_start'].apply(lambda x: x.isocalendar().week)

    sub = pork_df[pork_df['commodity'] == cut].copy()
    curr_yr = sub['Year'].max()
    curr = sub[sub['Year'] == curr_yr].groupby('iso_week')['value'].mean().reset_index()
    prev = sub[sub['Year'] == curr_yr - 1].groupby('iso_week')['value'].mean().reset_index()
    merged = curr.merge(prev, on='iso_week', suffixes=('', '_prev')).dropna()
    merged['pct'] = (merged['value'] - merged['value_prev']) / merged['value_prev'] * 100

    fig = go.Figure(go.Bar(
        x=merged['iso_week'], y=merged['pct'],
        marker_color=[GREEN if v >= 0 else RED for v in merged['pct']],
        marker_line_width=0,
        hovertemplate=f'Week %{{x}}: %{{y:.1f}}%<extra>{cut}</extra>',
    ))
    fig.add_hline(y=0, line_color='rgba(100,100,100,0.3)', line_width=1)
    fig.update_layout(**_L(height=height, ysuffix='%'))
    fig.update_xaxes(title_text='Week of Year', color=SUB, title_font=dict(size=10))
    return to_json(fig)

# ══════════════════════════════════════════════════════════════════════════════
# CASH vs FUTURES — HOG CHARTS
# ══════════════════════════════════════════════════════════════════════════════

def _prep_hog_basis(cash_df, futures_df):
    cc = cash_df.copy()
    cc['report_date'] = pd.to_datetime(cc['report_date'], errors='coerce')
    cc = cc[cc['name'] == 'National'].dropna(subset=['wtd_avg'])
    cc['week_start'] = cc['report_date'] - pd.to_timedelta(cc['report_date'].dt.weekday, unit='D')
    cc['Year'] = cc['report_date'].dt.year
    cash = cc.groupby(['week_start', 'Year'])['wtd_avg'].mean().reset_index()
    ep = futures_df.copy()
    ep['trading_day'] = pd.to_datetime(ep['trading_day'], errors='coerce')
    he = ep[ep['commodity'] == 'HE'].copy()
    month_map = {'G': 2, 'J': 4, 'M': 6, 'N': 7, 'Q': 8, 'V': 10, 'Z': 12}
    he['month_num'] = he['month'].map(month_map)
    he = he.dropna(subset=['month_num'])
    he['expiry_approx'] = pd.to_datetime(dict(year=he['year'], month=he['month_num'].astype(int), day=15))
    he = he.sort_values(['trading_day', 'expiry_approx'])
    nearby = he[he['expiry_approx'] >= he['trading_day']].groupby('trading_day').first().reset_index()
    nearby['week_start'] = nearby['trading_day'] - pd.to_timedelta(nearby['trading_day'].dt.weekday, unit='D')
    nearby['Year'] = nearby['trading_day'].dt.year
    fut = nearby.groupby(['week_start', 'Year'])['close'].mean().reset_index()
    merged = cash.merge(fut, on=['week_start', 'Year'], how='inner')
    merged['basis'] = merged['wtd_avg'] - merged['close']
    merged['rolling_basis'] = merged['basis'].rolling(4, min_periods=1).mean()
    merged['doy'] = pd.to_datetime(merged['week_start']).dt.dayofyear
    merged['iso_week'] = pd.to_datetime(merged['week_start']).apply(lambda x: x.isocalendar().week)
    return merged.sort_values('week_start')


def chart_hog_cash_vs_futures(cash_df, futures_df, height=310):
    basis_df = _prep_hog_basis(cash_df, futures_df)
    curr_yr = basis_df['Year'].max()
    sub = _drop_partial(basis_df[basis_df['Year'] == curr_yr].sort_values('week_start').copy(), 'wtd_avg')
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sub['doy'], y=sub['wtd_avg'],
        mode='lines+markers', name='Cash (National)',
        line=dict(color=GOLD, width=2.5), marker=dict(size=4),
        connectgaps=False, hovertemplate='Cash: $%{y:.2f}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=sub['doy'], y=sub['close'],
        mode='lines+markers', name='Nearby Futures (HE)',
        line=dict(color=BLUE, width=2.5), marker=dict(size=4),
        connectgaps=False, hovertemplate='Futures: $%{y:.2f}<extra></extra>',
    ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(**MON_TICKS)
    return to_json(fig)


def chart_hog_basis_rolling(cash_df, futures_df, height=290):
    basis_df = _prep_hog_basis(cash_df, futures_df)
    curr_yr = basis_df['Year'].max()
    sub = _drop_partial(basis_df[basis_df['Year'] == curr_yr].sort_values('week_start').copy(), 'basis')
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sub['doy'], y=sub['basis'],
        marker_color=[GREEN if v >= 0 else RED for v in sub['basis']],
        marker_line_width=0, name='Weekly basis',
        hovertemplate='Basis: $%{y:.2f}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=sub['doy'], y=sub['rolling_basis'],
        mode='lines', name='4-wk avg',
        line=dict(color=GOLD, width=2),
        connectgaps=False, hovertemplate='4-wk: $%{y:.2f}<extra></extra>',
    ))
    fig.add_hline(y=0, line_color='rgba(255,255,255,0.15)', line_width=1)
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(**MON_TICKS)
    return to_json(fig)


def chart_hog_basis_by_month(cash_df, futures_df, height=280):
    basis_df = _prep_hog_basis(cash_df, futures_df)
    basis_df['month'] = pd.to_datetime(basis_df['week_start']).dt.month
    month_names = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',
                   7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
    avg = basis_df.groupby('month')['basis'].mean().reset_index()
    avg['month_name'] = avg['month'].map(month_names)
    fig = go.Figure(go.Bar(
        x=avg['month_name'], y=avg['basis'],
        marker_color=[GREEN if v >= 0 else RED for v in avg['basis']],
        marker_line_width=0,
        hovertemplate='%{x}: $%{y:.2f}<extra></extra>',
    ))
    fig.add_hline(y=0, line_color='rgba(255,255,255,0.2)', line_width=1)
    fig.update_layout(**_L(height=height, yprefix='$'))
    return to_json(fig)


def chart_he_futures_curve(futures_df, height=290):
    ep = futures_df.copy()
    ep['trading_day'] = pd.to_datetime(ep['trading_day'], errors='coerce')
    he = ep[ep['commodity'] == 'HE'].copy()
    latest = he['trading_day'].max()
    curve = he[he['trading_day'] == latest].copy()
    month_order = ['G','J','M','N','Q','V','Z']
    month_names = {'G':'Feb','J':'Apr','M':'Jun','N':'Jul','Q':'Aug','V':'Oct','Z':'Dec'}
    curve['m_num'] = curve['month'].apply(lambda m: month_order.index(m) if m in month_order else 99)
    curve = curve.sort_values('m_num')
    curve['label'] = curve['month'].map(month_names).fillna(curve['month']) + ' ' + curve['year'].astype(str)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=curve['label'], y=curve['close'],
        mode='lines+markers',
        line=dict(color=BLUE, width=2.5),
        marker=dict(size=9, color=BLUE, line=dict(color='#111827', width=2)),
        name='Lean Hog Futures',
        hovertemplate='%{x}: $%{y:.2f}/cwt<extra></extra>',
    ))
    fig.update_layout(**_L(height=height, yprefix='$'))
    fig.update_xaxes(title_text='Contract Month', color=SUB, title_font=dict(size=10))
    return to_json(fig)