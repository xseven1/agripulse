import json
import pandas as pd
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from core.services import data_loader as dl
from core.services import chart_builder as cb
from core.services import ai_engine as ai
from core.services import comparable_weeks as cw_service


# ── HELPERS ────────────────────────────────────────────────────────────────────

def _safe_chart(fn, *args, **kwargs):
    try:
        return json.dumps(fn(*args, **kwargs))
    except Exception as e:
        return json.dumps({'data': [], 'layout': {'title': f'Chart unavailable: {str(e)}',
            'paper_bgcolor': 'rgba(0,0,0,0)', 'plot_bgcolor': '#111827',
            'font': {'color': '#A0AEC0'}, 'height': 300}})


def _rich_slaughter_summary(df, carcass_df):
    """12 weeks of slaughter + carcass weights for module insight."""
    if df.empty:
        return {}
    df = df.copy()
    df['slaughter_date'] = pd.to_datetime(df['slaughter_date'])
    recent = df[df['slaughter_date'] >= df['slaughter_date'].max() - pd.Timedelta(weeks=12)]
    cw = carcass_df.copy()
    cw['report_date'] = pd.to_datetime(cw['report_date'])
    cw_recent = cw[cw['report_date'] >= cw['report_date'].max() - pd.Timedelta(weeks=12)]
    return {
        'slaughter': recent[['slaughter_date','commodity','slaughter','year_ago','week_ago']].dropna().to_dict(orient='records'),
        'carcass_weights': cw_recent[['report_date','avg_carcass_weight','purchase_type']].dropna().to_dict(orient='records'),
    }


def _rich_cutout_summary(cutout_df, primal_df, pork_df):
    """12 weeks of cutout + 8 weeks of primals for module insight."""
    cutout_df = cutout_df.copy()
    cutout_df['report_date'] = pd.to_datetime(cutout_df['report_date'])
    recent_cutout = cutout_df[cutout_df['report_date'] >= cutout_df['report_date'].max() - pd.Timedelta(weeks=12)]
    primal_df = primal_df.copy()
    primal_df['report_date'] = pd.to_datetime(primal_df['report_date'])
    recent_primal = primal_df[primal_df['report_date'] >= primal_df['report_date'].max() - pd.Timedelta(weeks=8)]
    return {
        'cutout': recent_cutout[['report_date','attribute','value']].dropna().to_dict(orient='records'),
        'beef_primals': recent_primal[['report_date','primal_desc','choice_600_900']].dropna().to_dict(orient='records'),
    }


def _rich_basis_summary(cash_df, futures_df):
    """12 weeks of cash + futures for module insight."""
    cash_df = cash_df.copy()
    cash_df['report_date'] = pd.to_datetime(cash_df['report_date'])
    futures_df = futures_df.copy()
    futures_df['trading_day'] = pd.to_datetime(futures_df['trading_day'])
    cash_recent = cash_df[cash_df['report_date'] >= cash_df['report_date'].max() - pd.Timedelta(weeks=12)]
    fut_recent = futures_df[futures_df['trading_day'] >= futures_df['trading_day'].max() - pd.Timedelta(weeks=12)]
    return {
        'cash': cash_recent[['report_date','weighted_avg_price']].dropna().to_dict(orient='records'),
        'futures': fut_recent[['trading_day','commodity','close']].dropna().to_dict(orient='records'),
    }


def _rich_wasde_summary(wasde_df):
    """All WASDE rows for beef/pork/livestock commodities."""
    df = wasde_df.copy()
    df['report_date'] = pd.to_datetime(df['report_date'])
    relevant = df[df['commodity'].isin(['Beef','Pork','Steers','Barrows and gilts'])]
    return relevant[['report_date','commodity','attribute','value','market_year']].dropna().to_dict(orient='records')


# ── DASHBOARD ──────────────────────────────────────────────────────────────────

def dashboard(request):
    # KPI data
    try:
        kpi_slaughter = dl.get_dashboard_kpis().to_dict(orient='records')
    except Exception:
        kpi_slaughter = []
    try:
        kpi_cutout = dl.get_dashboard_cutout_kpi().to_dict(orient='records')
    except Exception:
        kpi_cutout = []
    try:
        kpi_cash = dl.get_dashboard_cash_kpi().to_dict(orient='records')
    except Exception:
        kpi_cash = []

    kpis = _compute_dashboard_kpis(kpi_slaughter, kpi_cutout, kpi_cash)

    # Dashboard charts
    charts = {}
    try:
        slaughter_df = dl.get_slaughter_all()
        cow_df = dl.get_cow_harvest()
        cutout_df = dl.get_cutout_all()
        primal_df = dl.get_cattle_primals()
        cash_df = dl.get_cash_cattle_all()
        futures_df = dl.get_futures_endpoint_all()
        charts = {
            'slaughter_sparkline': json.dumps(cb.chart_dashboard_slaughter_sparkline(slaughter_df)),
            'species_mix':         json.dumps(cb.chart_dashboard_species_mix(slaughter_df)),
            'cow_donut':           json.dumps(cb.chart_dashboard_cow_donut(cow_df)),
            'cutout_sparkline':    json.dumps(cb.chart_dashboard_cutout_sparkline(cutout_df)),
            'primal_heatmap':      json.dumps(cb.chart_dashboard_primal_heatmap(primal_df)),
            'cutout_vs_avg':       json.dumps(cb.chart_dashboard_cutout_vs_avg(cutout_df)),
            'cash_futures_spark':  json.dumps(cb.chart_dashboard_cash_futures_sparkline(cash_df, futures_df)),
            'basis_gauge':         json.dumps(cb.chart_dashboard_basis_gauge(cash_df, futures_df)),
        }
    except Exception as e:
        charts = {}

    try:
        cross_signal = ai.generate_cross_signal_insight({})
    except Exception:
        cross_signal = 'Select a module below to begin your market analysis.'

    return render(request, 'dashboard.html', {
        'cross_signal': cross_signal,
        'kpis': kpis,
        'charts': charts,
    })


def _compute_dashboard_kpis(slaughter_rows, cutout_rows, cash_rows):
    """Compute WoW changes for dashboard KPI cards."""
    kpis = {}
    try:
        for row in slaughter_rows:
            commodity = row['commodity']
            curr = row['slaughter']
            prev = row['week_ago']
            if curr and prev and prev > 0:
                wow = (curr - prev) / prev * 100
                kpis[commodity.lower() + '_slaughter'] = {
                    'value': f"{curr:,.0f}",
                    'delta': f"{wow:+.1f}%",
                    'signal': 'bear' if wow > 2 else ('bull' if wow < -2 else 'neut'),
                    'note': 'head vs last week',
                }
    except Exception:
        pass

    try:
        cutout_by_attr = {}
        for row in cutout_rows:
            attr = row['attribute']
            cutout_by_attr.setdefault(attr, []).append(row['value'])
        for attr in ['Choice', 'Select']:
            if attr in cutout_by_attr and len(cutout_by_attr[attr]) >= 2:
                vals = cutout_by_attr[attr]
                curr, prev = vals[0], vals[1]
                wow = curr - prev
                kpis[attr.lower() + '_cutout'] = {
                    'value': f"${curr:.2f}",
                    'delta': f"{wow:+.2f}",
                    'signal': 'bull' if wow > 0 else ('bear' if wow < 0 else 'neut'),
                    'note': '$/cwt vs last reading',
                }
        if 'Choice' in cutout_by_attr and 'Select' in cutout_by_attr:
            choice_curr = cutout_by_attr['Choice'][0]
            select_curr = cutout_by_attr['Select'][0]
            choice_prev = cutout_by_attr['Choice'][1] if len(cutout_by_attr['Choice']) > 1 else choice_curr
            select_prev = cutout_by_attr['Select'][1] if len(cutout_by_attr['Select']) > 1 else select_curr
            spread_curr = choice_curr - select_curr
            spread_prev = choice_prev - select_prev
            wow = spread_curr - spread_prev
            kpis['spread'] = {
                'value': f"${spread_curr:.2f}",
                'delta': f"+{wow:.2f} widening" if wow > 0 else f"{abs(wow):.2f} narrowing",
                'signal': 'bull' if wow > 0 else ('bear' if wow < 0 else 'neut'),
                'note': 'Choice/Select spread',
            }
    except Exception:
        pass

    try:
        if len(cash_rows) >= 2:
            curr = cash_rows[0]['weighted_avg_price']
            prev = cash_rows[1]['weighted_avg_price']
            if curr and prev and prev > 0:
                wow = curr - prev
                kpis['cash_price'] = {
                    'value': f"${curr:.2f}",
                    'delta': f"{wow:+.2f}",
                    'signal': 'bull' if wow > 0 else ('bear' if wow < 0 else 'neut'),
                    'note': '$/cwt vs prev day',
                }
    except Exception:
        pass

    return kpis


def _compute_slaughter_kpis(slaughter_rows, carcass_rows):
    """WoW KPIs for slaughter module."""
    kpis = {}
    try:
        by_commodity = {}
        for row in slaughter_rows:
            by_commodity.setdefault(row['commodity'], []).append(row['total'])
        for commodity in ['Cattle', 'Hogs']:
            if commodity in by_commodity and len(by_commodity[commodity]) >= 2:
                curr, prev = by_commodity[commodity][0], by_commodity[commodity][1]
                wow = (curr - prev) / prev * 100 if prev > 0 else 0
                key = commodity.lower()
                kpis[key] = {
                    'value': f"{curr:,.0f}",
                    'delta': f"{wow:+.1f}%",
                    'signal': 'bear' if wow > 2 else ('bull' if wow < -2 else 'neut'),
                    'note': 'head WoW',
                }
    except Exception:
        pass
    try:
        if len(carcass_rows) >= 2:
            curr = carcass_rows[0]['avg_carcass_weight']
            prev = carcass_rows[1]['avg_carcass_weight']
            if curr and prev:
                delta = curr - prev
                kpis['carcass'] = {
                    'value': f"{curr:.1f} lbs",
                    'delta': f"{delta:+.1f} lbs",
                    'signal': 'bear' if delta > 2 else ('bull' if delta < -2 else 'neut'),
                    'note': 'avg carcass weight WoW',
                }
    except Exception:
        pass
    return kpis


def _compute_cutout_kpis(cutout_rows, primal_rows):
    """WoW KPIs for cutout module."""
    kpis = {}
    try:
        by_attr = {}
        for row in cutout_rows:
            by_attr.setdefault(row['attribute'], []).append(row['value'])
        for attr in ['Choice', 'Select']:
            if attr in by_attr and len(by_attr[attr]) >= 2:
                curr, prev = by_attr[attr][0], by_attr[attr][1]
                delta = curr - prev
                kpis[attr.lower()] = {
                    'value': f"${curr:.2f}",
                    'delta': f"{delta:+.2f}",
                    'signal': 'bull' if delta > 0 else ('bear' if delta < 0 else 'neut'),
                    'note': '$/cwt WoW',
                }
        if 'Choice' in by_attr and 'Select' in by_attr:
            spread = by_attr['Choice'][0] - by_attr['Select'][0]
            prev_spread = (by_attr['Choice'][1] - by_attr['Select'][1]) if len(by_attr['Choice']) > 1 else spread
            delta = spread - prev_spread
            kpis['spread'] = {
                'value': f"${spread:.2f}",
                'delta': f"{delta:+.2f} {'widening' if delta > 0 else 'narrowing'}",
                'signal': 'bull' if delta > 0 else ('bear' if delta < 0 else 'neut'),
                'note': 'Choice/Select spread',
            }
    except Exception:
        pass
    try:
        if not primal_rows.empty:
            top = primal_rows.iloc[0]
            bot = primal_rows.iloc[-1]
            kpis['top_primal'] = {
                'value': top['primal_desc'],
                'delta': f"+{top['delta']:.2f}",
                'signal': 'bull',
                'note': 'top gaining primal',
            }
            kpis['bot_primal'] = {
                'value': bot['primal_desc'],
                'delta': f"{bot['delta']:.2f}",
                'signal': 'bear',
                'note': 'top losing primal',
            }
    except Exception:
        pass
    return kpis


def _compute_basis_kpis(cash_rows, futures_rows):
    """WoW KPIs for cash/futures module."""
    kpis = {}
    try:
        if len(cash_rows) >= 2:
            curr = cash_rows[0]['weighted_avg_price']
            prev = cash_rows[1]['weighted_avg_price']
            delta = curr - prev
            kpis['cash'] = {
                'value': f"${curr:.2f}",
                'delta': f"{delta:+.2f}",
                'signal': 'bull' if delta > 0 else ('bear' if delta < 0 else 'neut'),
                'note': '$/cwt live WoW',
            }
    except Exception:
        pass
    try:
        if len(futures_rows) >= 2:
            curr = futures_rows[0]['close']
            prev = futures_rows[1]['close']
            delta = curr - prev
            kpis['futures'] = {
                'value': f"${curr:.2f}",
                'delta': f"{delta:+.2f}",
                'signal': 'bull' if delta > 0 else ('bear' if delta < 0 else 'neut'),
                'note': 'LE nearby futures WoW',
            }
        if len(cash_rows) >= 1 and len(futures_rows) >= 1:
            basis = cash_rows[0]['weighted_avg_price'] - futures_rows[0]['close']
            kpis['basis'] = {
                'value': f"${basis:.2f}",
                'delta': 'cash above futures' if basis > 0 else 'cash below futures',
                'signal': 'bull' if basis > 0 else 'bear',
                'note': 'current basis',
            }
    except Exception:
        pass
    return kpis


def _compute_lrp_kpis(lrp_rows):
    """KPIs for LRP module."""
    kpis = {}
    try:
        if lrp_rows:
            row = lrp_rows[0]
            kpis['futures'] = {
                'value': f"${row['futures_price']:.2f}",
                'delta': 'current futures price',
                'signal': 'neut',
                'note': 'Live Cattle futures',
            }
            kpis['coverage'] = {
                'value': f"${row['coverage_price']:.2f}",
                'delta': f"{row['coverage_level_percent']*100:.0f}% coverage level",
                'signal': 'bull',
                'note': 'LRP floor at 95%',
            }
            kpis['premium'] = {
                'value': f"${row['per_head_premium']:.2f}",
                'delta': f"{row['subsidy_percent']*100:.0f}% USDA subsidized",
                'signal': 'neut',
                'note': 'producer premium/head',
            }
    except Exception:
        pass
    return kpis


def _compute_wasde_kpis(wasde_rows):
    """KPIs for WASDE module."""
    kpis = {}
    try:
        by_commodity = {}
        for row in wasde_rows:
            by_commodity.setdefault(row['commodity'], []).append(row['value'])
        for commodity in ['Beef', 'Pork']:
            if commodity in by_commodity and len(by_commodity[commodity]) >= 2:
                curr, prev = by_commodity[commodity][0], by_commodity[commodity][1]
                delta = curr - prev
                kpis[commodity.lower()] = {
                    'value': f"{curr:,.0f}M lbs",
                    'delta': f"{delta:+,.0f} vs prior report",
                    'signal': 'bear' if delta > 0 else ('bull' if delta < 0 else 'neut'),
                    'note': f'{commodity} production forecast',
                }
    except Exception:
        pass
    return kpis


# ── SLAUGHTER ──────────────────────────────────────────────────────────────────

def slaughter(request):
    slaughter_df = dl.get_slaughter_all()
    carcass_df = dl.get_carcass_weights()
    cow_df = dl.get_cow_harvest()
    summary = _rich_slaughter_summary(slaughter_df, carcass_df)
    # Separate cattle and hog insights
    cattle_summary = {k: v for k, v in summary.items() if True}
    hog_summary = summary
    insight_cattle = ai.generate_module_insight('slaughter_cattle', {
        'species': 'Cattle',
        'data': [r for r in summary.get('slaughter', []) if r.get('commodity') == 'Cattle'],
        'carcass': summary.get('carcass_weights', []),
    })
    insight_hogs = ai.generate_module_insight('slaughter_hogs', {
        'species': 'Hogs',
        'data': [r for r in summary.get('slaughter', []) if r.get('commodity') == 'Hogs'],
    })
    insight = insight_cattle  # default for combined
    # KPI cards
    try:
        kpi_rows = dl.get_slaughter_kpis().to_dict(orient='records')
        carcass_rows = dl.get_carcass_kpis().to_dict(orient='records')
        kpis = _compute_slaughter_kpis(kpi_rows, carcass_rows)
    except Exception:
        kpis = {}

    charts = {
        'slaughter_seasonal_cattle':  _safe_chart(cb.chart_slaughter_seasonal, slaughter_df, 'Cattle'),
        'slaughter_seasonal_hogs':    _safe_chart(cb.chart_slaughter_seasonal, slaughter_df, 'Hogs', cb.BLUE),
        'slaughter_yoy_cattle':       _safe_chart(cb.chart_slaughter_yoy_pct, slaughter_df, 'Cattle'),
        'slaughter_yoy_hogs':         _safe_chart(cb.chart_slaughter_yoy_pct, slaughter_df, 'Hogs'),
        'hogs_vs_cattle':             _safe_chart(cb.chart_hogs_vs_cattle, slaughter_df),
        'cow_slaughter':              _safe_chart(cb.chart_cow_slaughter, cow_df),
        'ytd_cattle':                 _safe_chart(cb.chart_ytd_slaughter, slaughter_df, 'Cattle'),
        'ytd_hogs':                   _safe_chart(cb.chart_ytd_slaughter, slaughter_df, 'Hogs'),
        'implied_beef':               _safe_chart(cb.chart_implied_production, slaughter_df, carcass_df, 'Cattle'),
        'implied_pork':               _safe_chart(cb.chart_implied_production, slaughter_df, carcass_df, 'Hogs'),
        'carcass_weights':            _safe_chart(cb.chart_carcass_weights, carcass_df),
    }
    return render(request, 'slaughter.html', {
        'charts': {k: v for k, v in charts.items()},
        'insight': insight,
        'insight_cattle': insight_cattle,
        'insight_hogs': insight_hogs,
        'kpis': kpis,
        'module': 'slaughter',
    })


# ── CUTOUT ─────────────────────────────────────────────────────────────────────

def cutout(request):
    cutout_df = dl.get_cutout_all()
    primal_df = dl.get_cattle_primals()
    pork_df_raw = dl.get_pork_primals()
    summary = _rich_cutout_summary(cutout_df, primal_df, pork_df_raw)
    insight = ai.generate_module_insight('cutout', summary)
    try:
        cutout_rows = dl.get_cutout_kpis().to_dict(orient='records')
        primal_rows = dl.get_primal_kpis()
        kpis = _compute_cutout_kpis(cutout_rows, primal_rows)
    except Exception:
        kpis = {}

    charts = {
        'cutout_seasonal':      _safe_chart(cb.chart_cutout_seasonal, cutout_df),
        'choice_select_spread': _safe_chart(cb.chart_choice_select_spread, cutout_df),
        'choice_yoy':           _safe_chart(cb.chart_cutout_yoy_pct, cutout_df, 'Choice'),
        'select_yoy':           _safe_chart(cb.chart_cutout_yoy_pct, cutout_df, 'Select'),
        'beef_primals':         _safe_chart(cb.chart_beef_primals, primal_df),
        'pork_primals':         _safe_chart(cb.chart_pork_primals, pork_df_raw),
        'seasonal_avg_cutout':  _safe_chart(cb.chart_seasonal_avg_cutout, cutout_df),
    }
    return render(request, 'cutout.html', {
        'charts': {k: v for k, v in charts.items()},
        'insight': insight,
        'kpis': kpis,
        'module': 'cutout',
    })


# ── CASH vs FUTURES ────────────────────────────────────────────────────────────

def cash_futures(request):
    cash_df = dl.get_cash_cattle_all()
    futures_df = dl.get_futures_endpoint_all()
    summary = _rich_basis_summary(cash_df, futures_df)
    insight = ai.generate_module_insight('cash_futures', summary)
    try:
        cash_rows, futures_rows = dl.get_basis_kpis()
        kpis = _compute_basis_kpis(
            cash_rows.to_dict(orient='records'),
            futures_rows.to_dict(orient='records')
        )
    except Exception:
        kpis = {}

    charts = {
        'cash_vs_futures': _safe_chart(cb.chart_cash_vs_futures, cash_df, futures_df),
        'basis_rolling':   _safe_chart(cb.chart_basis_rolling, cash_df, futures_df),
        'basis_band':      _safe_chart(cb.chart_basis_band, cash_df, futures_df),
        'basis_by_month':  _safe_chart(cb.chart_basis_by_month, cash_df, futures_df),
        'futures_curve':   _safe_chart(cb.chart_futures_curve, futures_df),
    }
    return render(request, 'cash_futures.html', {
        'charts': {k: v for k, v in charts.items()},
        'insight': insight,
        'kpis': kpis,
        'module': 'cash_futures',
    })


# ── LRP ────────────────────────────────────────────────────────────────────────

def lrp(request):
    commodity = request.GET.get('commodity', 'LIVE CATTLE')
    lrp_df = dl.get_lrp_all()
    summary = lrp_df[['commodity','coverage_level_percent','coverage_price','per_head_premium','futures_price','endorsement_length','subsidy_percent']].dropna().to_dict(orient='records')
    insight = ai.generate_module_insight('lrp', summary)
    try:
        lrp_rows = dl.get_lrp_kpis().to_dict(orient='records')
        kpis = _compute_lrp_kpis(lrp_rows)
    except Exception:
        kpis = {}

    charts = {
        'lrp_coverage_vs_futures': _safe_chart(cb.chart_lrp_coverage_vs_futures, lrp_df, commodity),
        'lrp_premium_curve':       _safe_chart(cb.chart_lrp_premium_curve, lrp_df, commodity),
        'lrp_net_floor':           _safe_chart(cb.chart_lrp_net_floor, lrp_df, commodity),
        'lrp_subsidy':             _safe_chart(cb.chart_lrp_subsidy_value, lrp_df, commodity),
    }
    return render(request, 'lrp.html', {
        'charts': {k: v for k, v in charts.items()},
        'insight': insight,
        'kpis': kpis,
        'commodity': commodity,
        'commodities': ['LIVE CATTLE', 'FDR CATTLE', 'CME LEAN HOGS'],
        'module': 'lrp',
    })


# ── WASDE ──────────────────────────────────────────────────────────────────────

def wasde(request):
    wasde_df = dl.get_wasde_all()
    summary = _rich_wasde_summary(wasde_df)
    insight = ai.generate_module_insight('wasde', summary)
    try:
        wasde_rows = dl.get_wasde_kpis().to_dict(orient='records')
        kpis = _compute_wasde_kpis(wasde_rows)
    except Exception:
        kpis = {}

    charts = {
        'wasde_production_beef': _safe_chart(cb.chart_wasde_production, wasde_df, 'Beef'),
        'wasde_production_pork': _safe_chart(cb.chart_wasde_production, wasde_df, 'Pork'),
        'wasde_revisions':       _safe_chart(cb.chart_wasde_revisions, wasde_df),
        'wasde_price_forecasts': _safe_chart(cb.chart_wasde_price_forecasts, wasde_df),
        'wasde_supply_demand':   _safe_chart(cb.chart_wasde_supply_demand, wasde_df, 'Beef'),
    }
    return render(request, 'wasde.html', {
        'charts': {k: v for k, v in charts.items()},
        'insight': insight,
        'kpis': kpis,
        'module': 'wasde',
    })




# ── API: CHART PERIOD TOGGLE ───────────────────────────────────────────────────

@require_GET
def api_chart_period(request, chart_id):
    """Return chart JSON filtered to requested period."""
    period = request.GET.get('period', 'year')
    module = request.GET.get('module', '')

    try:
        chart_json = _get_chart_for_period(chart_id, period)
        return JsonResponse({'chart': chart_json})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def _get_chart_for_period(chart_id, period):
    """Build chart JSON for a specific chart_id and period."""
    import json as json_mod

    def apply_period_xaxis(chart_dict, period):
        """Apply period-appropriate x-axis labels to chart JSON."""
        if not chart_dict or 'layout' not in chart_dict:
            return chart_dict
        xaxis_settings = cb._period_xaxis(period)
        if 'xaxis' not in chart_dict['layout']:
            chart_dict['layout']['xaxis'] = {}
        chart_dict['layout']['xaxis'].update(xaxis_settings)
        return chart_dict

    # Slaughter charts
    if chart_id == 'slaughter_seasonal_cattle':
        df = dl.get_slaughter_all()
        df = cb._slice_period(df, 'slaughter_date', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_slaughter_seasonal(df, 'Cattle'))), period)

    elif chart_id == 'slaughter_seasonal_hogs':
        df = dl.get_slaughter_all()
        df = cb._slice_period(df, 'slaughter_date', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_slaughter_seasonal(df, 'Hogs', cb.BLUE))), period)

    elif chart_id == 'slaughter_yoy_cattle':
        df = dl.get_slaughter_all()
        df = cb._slice_period(df, 'slaughter_date', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_slaughter_yoy_pct(df, 'Cattle'))), period)

    elif chart_id == 'slaughter_yoy_hogs':
        df = dl.get_slaughter_all()
        df = cb._slice_period(df, 'slaughter_date', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_slaughter_yoy_pct(df, 'Hogs'))), period)

    elif chart_id == 'hogs_vs_cattle':
        df = dl.get_slaughter_all()
        df = cb._slice_period(df, 'slaughter_date', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_hogs_vs_cattle(df))), period)

    elif chart_id == 'carcass_weights':
        df = dl.get_carcass_weights()
        df = cb._slice_period(df, 'report_date', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_carcass_weights(df))), period)

    # Cutout charts
    elif chart_id == 'cutout_seasonal':
        df = dl.get_cutout_all()
        df = cb._slice_period(df, 'report_date', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_cutout_seasonal(df))), period)

    elif chart_id == 'choice_select_spread':
        df = dl.get_cutout_all()
        df = cb._slice_period(df, 'report_date', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_choice_select_spread(df))), period)

    elif chart_id == 'choice_yoy':
        df = dl.get_cutout_all()
        df = cb._slice_period(df, 'report_date', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_cutout_yoy_pct(df, 'Choice'))), period)

    elif chart_id == 'select_yoy':
        df = dl.get_cutout_all()
        df = cb._slice_period(df, 'report_date', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_cutout_yoy_pct(df, 'Select'))), period)

    elif chart_id == 'beef_primals':
        df = dl.get_cattle_primals()
        df = cb._slice_period(df, 'report_date', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_beef_primals(df))), period)

    elif chart_id == 'pork_primals':
        df = dl.get_pork_primals()
        df = cb._slice_period(df, 'report_date', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_pork_primals(df))), period)

    # Cash/Futures charts
    elif chart_id == 'cash_vs_futures':
        cash_df = dl.get_cash_cattle_all()
        futures_df = dl.get_futures_endpoint_all()
        cash_df = cb._slice_period(cash_df, 'report_date', period)
        futures_df = cb._slice_period(futures_df, 'trading_day', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_cash_vs_futures(cash_df, futures_df))), period)

    elif chart_id == 'basis_rolling':
        cash_df = dl.get_cash_cattle_all()
        futures_df = dl.get_futures_endpoint_all()
        cash_df = cb._slice_period(cash_df, 'report_date', period)
        futures_df = cb._slice_period(futures_df, 'trading_day', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_basis_rolling(cash_df, futures_df))), period)

    elif chart_id == 'basis_band':
        cash_df = dl.get_cash_cattle_all()
        futures_df = dl.get_futures_endpoint_all()
        cash_df = cb._slice_period(cash_df, 'report_date', period)
        futures_df = cb._slice_period(futures_df, 'trading_day', period)
        return apply_period_xaxis(json_mod.loads(json_mod.dumps(cb.chart_basis_band(cash_df, futures_df))), period)

    else:
        return {}

# ── COMPARABLE WEEK FINDER ─────────────────────────────────────────────────────

def comparable(request):
    target_week = request.GET.get('week', None)
    species = request.GET.get('species', 'cattle')
    matches = []
    target_metrics = {}
    ai_insight = ''
    error = ''

    try:
        if species == 'hogs':
            matrix = dl.get_hog_comparable_matrix()
            matrix['week'] = pd.to_datetime(matrix['week'])
            target_metrics = cw_service.get_hog_target_metrics(matrix, target_week)
            matches = cw_service.find_comparable_weeks_hogs(target_week, n=3)
            available_weeks = matrix.sort_values('week', ascending=False)['week'].dt.strftime('%Y-%m-%d').tolist()
        else:
            matrix = dl.get_comparable_week_matrix()
            matrix['week'] = pd.to_datetime(matrix['week'])
            latest = matrix.sort_values('week').iloc[-1]
            target_metrics = {
                'week': latest['week'].strftime('%b %d, %Y') if target_week is None else target_week,
                'choice_cutout': f"${latest['choice_cutout']:.2f}" if pd.notna(latest.get('choice_cutout')) else 'N/A',
                'select_cutout': f"${latest['select_cutout']:.2f}" if pd.notna(latest.get('select_cutout')) else 'N/A',
                'spread': f"${latest['spread']:.2f}" if pd.notna(latest.get('spread')) else 'N/A',
                'carcass_weight': f"{latest['carcass_weight']:.1f} lbs" if pd.notna(latest.get('carcass_weight')) else 'N/A',
                'cash_price': f"${latest['cash_price']:.2f}" if pd.notna(latest.get('cash_price')) else 'N/A',
                'week_of_year': int(latest['week_of_year']),
            }
            matches = cw_service.find_comparable_weeks(target_week, n=3)
            available_weeks = matrix.sort_values('week', ascending=False)['week'].dt.strftime('%Y-%m-%d').tolist()

        if matches:
            ai_insight = cw_service.get_ai_comparable_insight(target_metrics, matches)
    except Exception as e:
        error = str(e)
        available_weeks = []

    return render(request, 'comparable.html', {
        'matches': matches,
        'target_metrics': target_metrics,
        'ai_insight': ai_insight,
        'available_weeks': available_weeks[:52],
        'selected_week': target_week or '',
        'species': species,
        'error': error,
        'module': 'comparable',
    })

# ── CHATBOT ────────────────────────────────────────────────────────────────────

def chatbot_page(request):
    return render(request, 'chatbot.html', {'module': 'general'})


# ── API: GENERAL CHAT ──────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def api_chat(request):
    try:
        body = json.loads(request.body)
        message = body.get('message', '')
        module = body.get('module', 'general')
        context = body.get('context', {})
        history = body.get('history', [])
        if not message:
            return JsonResponse({'error': 'No message'}, status=400)
        response = ai.chat(message, module, context, history)
        return JsonResponse({'response': response})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── API: CHART AI INSIGHT ──────────────────────────────────────────────────────

@require_GET
def api_chart_insight(request, chart_id):
    """Generate 1-2 sentence AI insight for a specific chart."""
    try:
        # Build a minimal data summary for the requested chart
        summary = _get_chart_data_summary(chart_id)
        insight = ai.generate_chart_insight(chart_id, summary)
        return JsonResponse({'insight': insight})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── API: CHART QUESTION ────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def api_chart_ask(request, chart_id):
    """User asks a free-form question about a specific chart."""
    try:
        body = json.loads(request.body)
        question = body.get('question', '')
        history = body.get('history', [])
        if not question:
            return JsonResponse({'error': 'No question'}, status=400)
        summary = _get_chart_data_summary(chart_id)
        response = ai.ask_chart(chart_id, question, summary, history)
        return JsonResponse({'response': response})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── API: MODULE INSIGHTS ───────────────────────────────────────────────────────

@require_GET
def api_module_insight(request, module):
    try:
        loaders = {
            'slaughter': lambda: _slaughter_summary(dl.get_slaughter_summary()),
            'cutout': lambda: dl.get_cutout_summary().to_dict(orient='records'),
            'cash_futures': lambda: dl.get_basis_summary()[0].to_dict(orient='records'),
            'lrp': lambda: dl.get_lrp_summary().to_dict(orient='records'),
            'wasde': lambda: dl.get_wasde_summary().to_dict(orient='records'),
        }
        if module not in loaders:
            return JsonResponse({'error': 'Unknown module'}, status=404)
        summary = loaders[module]()
        insight = ai.generate_module_insight(module, summary)
        return JsonResponse({'insight': insight})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── DATA SUMMARY BUILDER ───────────────────────────────────────────────────────

def _get_chart_data_summary(chart_id):
    """Return a minimal data summary dict for a given chart_id."""
    try:
        if 'slaughter' in chart_id or 'ytd' in chart_id or 'implied' in chart_id or 'cow' in chart_id or 'hogs_vs' in chart_id or 'carcass' in chart_id:
            df = dl.get_slaughter_summary()
            return df.to_dict(orient='records')
        elif 'cutout' in chart_id or 'choice' in chart_id or 'select' in chart_id or 'primal' in chart_id or 'seasonal_avg' in chart_id:
            return dl.get_cutout_summary().to_dict(orient='records')
        elif 'basis' in chart_id or 'cash_vs' in chart_id or 'futures_curve' in chart_id:
            cash, fut = dl.get_basis_summary()
            return {'cash': cash.to_dict(orient='records'), 'futures': fut.to_dict(orient='records')}
        elif 'lrp' in chart_id:
            return dl.get_lrp_summary().to_dict(orient='records')
        elif 'wasde' in chart_id:
            return dl.get_wasde_summary().to_dict(orient='records')
        else:
            return {}
    except Exception:
        return {}
