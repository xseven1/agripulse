import json
import requests
from datetime import date
from django.conf import settings
from django.core.cache import cache

URL = 'https://openrouter.ai/api/v1/chat/completions'

def _strip_markdown(text):
    """Strip all markdown regardless of model behavior."""
    import re
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}(.*?)_{1,3}', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\*\-\•]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'`{1,3}', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


SYSTEM_BASE = """You are an agricultural market analyst for AgriPulse, used by livestock advisors.

OUTPUT FORMAT - MANDATORY - ANY VIOLATION MAKES YOUR RESPONSE WRONG:
Write ONLY plain numbered points. Example format: 1. First point here. 2. Second point here. 3. Third point here.
Do NOT use any of the following: asterisks, dashes at line start, underscores, pound signs, bold, italic, headers, bullet symbols, markdown of any kind.
Maximum 4 numbered points. One sentence each. Never speculate beyond the data."""

MODULE_PROMPTS = {
    'slaughter': "Analyze this slaughter pace and carcass weight data. Identify whether pace is running ahead or behind year-ago, what that implies for near-term beef supply, and any anomalies in carcass weights. Flag cross-signal issues if relevant.",
    'cutout': "Analyze this beef cutout value and primal data. Identify whether the Choice/Select spread is widening or narrowing, which primals are leading or lagging, and whether current cutout levels are historically elevated or depressed.",
    'cash_futures': "Analyze this cash cattle vs futures data. Identify whether basis is historically wide or tight, what it implies for producer hedging decisions, and any convergence or divergence trends worth flagging.",
    'lrp': "Analyze this LRP insurance quote data. Identify at current premium levels whether LRP provides meaningful downside protection, which coverage level and endorsement length offers the best tradeoff, and whether an advisor should recommend LRP over a straight futures hedge.",
    'wasde': "Analyze this WASDE report data. Identify the most significant revision and its market implications, whether supply or demand revisions are more bearish or bullish, and any divergence between WASDE projections and current market signals.",
}

CHART_PROMPTS = {
    # Slaughter
    'slaughter_seasonal_cattle': "This chart shows weekly cattle slaughter this year vs the 5-year historical range. Identify: is pace inside or outside the normal band, what weeks showed the biggest deviations, and what the current trend implies for near-term beef supply.",
    'slaughter_seasonal_hogs': "This chart shows weekly hog slaughter this year vs the 5-year historical range. Identify: is pace inside or outside normal bounds, any unusual spikes or dips, and what the current trajectory means for pork supply pressure.",
    'slaughter_yoy_cattle': "This chart shows cattle slaughter % change vs the same week last year. Identify: which weeks ran hot vs last year, which ran cold, and whether the trend is accelerating or decelerating into recent weeks.",
    'slaughter_yoy_hogs': "This chart shows hog slaughter % change vs the same week last year. Identify: which weeks ran hot or cold, whether the pace is consistent or erratic, and what the recent trend implies.",
    'hogs_vs_cattle': "This chart overlays cattle and hog slaughter % change vs year-ago. Identify: are both species moving in the same direction or diverging, what does a divergence signal about species-specific supply dynamics, and which species is driving more supply pressure.",
    'cow_slaughter': "This chart shows dairy cow vs other cow slaughter. Identify: which category is running higher than normal, what elevated cow slaughter implies about herd liquidation or expansion, and whether this is a bullish or bearish supply signal.",
    'ytd_cattle': "This chart shows YTD cumulative cattle slaughter this year vs last year. Identify: is the gap widening or narrowing, what the cumulative overhang or deficit means for annual supply balance, and at what pace the gap is changing.",
    'ytd_hogs': "This chart shows YTD cumulative hog slaughter this year vs last year. Identify: cumulative supply gap direction, whether it is widening or narrowing in recent weeks, and implications for annual pork supply.",
    'implied_beef': "This chart shows implied beef production (head × carcass weight). Identify: is total lbs trending up or down even if head count is flat, what a divergence between head count and production implies, and whether heavier animals are offsetting fewer head.",
    'implied_pork': "This chart shows implied pork production (head × carcass weight). Identify: total production trend, whether weight gains are compensating for any head count changes, and what this means for total pork supply.",
    'carcass_weights': "This chart shows average carcass weights vs the 5-year historical band. Identify: are weights inside or outside the normal range, is the 4-week trend rising or falling, and what heavier or lighter carcass weights imply for packer margins and total beef output.",
    # Cutout
    'cutout_seasonal': "This chart shows Choice and Select cutout values this year vs the 5-year historical band. Identify: are current prices inside or outside the historical range, which grade is performing better, and what the current level implies about retail beef demand.",
    'choice_select_spread': "This chart shows the Choice minus Select spread over time with the historical average. Identify: is the spread widening or narrowing vs history, what a widening spread signals about quality demand, and whether the current reading is unusual.",
    'choice_yoy': "This chart shows Choice cutout % change vs the same week last year. Identify: has Choice consistently outperformed or underperformed last year, which weeks were outliers, and what the recent trend implies.",
    'select_yoy': "This chart shows Select cutout % change vs the same week last year. Identify: is Select telling the same story as Choice or diverging, and what a divergence between the two grades implies about demand quality.",
    'beef_primals': "This chart shows all beef primal cut values this year. Identify: which primals are leading the move up or down, which are lagging, and what the relative strength of high-value cuts like rib and loin vs lower-value cuts implies about overall cutout direction.",
    'pork_primals': "This chart shows all pork primal cut values this year. Identify: which cuts are strongest and weakest, whether belly is leading the market, and what the primal spread implies about pork demand quality.",
    'seasonal_avg_cutout': "This chart shows the historical average seasonal pattern for Choice and Select. Identify: where we are in the typical seasonal cycle, whether current prices are tracking above or below the historical average for this time of year, and what the seasonal pattern predicts for the next 4-8 weeks.",
    # Cash/Futures
    'cash_vs_futures': "This chart shows cash cattle price vs nearby Live Cattle futures on the same axis. Identify: is cash above or below futures, is the gap widening or narrowing, and what the relationship implies for producer and packer incentives.",
    'basis_rolling': "This chart shows weekly basis (cash minus futures) with a 4-week rolling average. Identify: is basis positive or negative, is the trend improving or deteriorating for producers, and what the rolling average suggests about the near-term direction.",
    'basis_band': "This chart shows current basis vs the 5-year historical range. Identify: is the current basis unusually wide or tight relative to history, what an unusually strong or weak basis implies for hedging decisions, and whether the current reading is an outlier.",
    'basis_by_month': "This chart shows average basis by calendar month across all historical years. Identify: which months historically show the strongest and weakest basis, where the current month falls in that seasonal pattern, and what advisors should know heading into the next few months.",
    'futures_curve': "This chart shows the Live Cattle futures curve — price by contract month. Identify: is the market in contango (deferred higher) or backwardation (deferred lower), what the shape of the curve implies about market expectations for future supply and demand, and whether the current structure favors or discourages forward pricing.",
    # LRP
    'lrp_coverage_vs_futures': "This chart shows LRP coverage price vs the current futures price by endorsement length. Identify: which endorsement lengths provide the most protection relative to current futures, at which coverage levels the floor begins to approach the futures price, and whether current LRP pricing is attractive relative to market levels.",
    'lrp_premium_curve': "This chart shows LRP producer premium cost per head by coverage level and endorsement length. Identify: how steeply premiums rise from 90% to 100% coverage, which endorsement length offers the best cost-per-point-of-protection, and at what coverage level premium costs become prohibitive.",
    'lrp_net_floor': "This chart shows whether the LRP net floor (coverage price minus premium) beats a straight futures hedge. Identify: at which coverage levels LRP provides a better floor than selling futures outright, and what the data implies about the optimal coverage level for a typical 500-head cattle operation.",
    'lrp_subsidy': "This chart shows the split between producer cost and USDA subsidy for LRP premiums. Identify: at which coverage levels the government subsidy is most valuable, how much the subsidy reduces the true cost of protection, and whether the subsidy makes higher coverage levels effectively cheaper on a risk-adjusted basis.",
    # WASDE
    'wasde_production': "This chart shows WASDE beef or pork production forecasts across report dates by market year. Identify: which market year has seen the most significant revision, whether production is being revised up or down in recent reports, and what the revision direction implies for price outlook.",
    'wasde_revisions': "This chart shows the largest WASDE month-over-month revisions. Identify: which commodity and attribute had the biggest revision, whether the largest revisions are supply-side or demand-side, and what the net effect of recent revisions is for cattle and hog price outlook.",
    'wasde_price_forecasts': "This chart shows WASDE price forecasts for steers and barrows/gilts across report dates. Identify: are forecast prices being revised up or down, is the USDA becoming more or less bullish on livestock prices, and how the current forecast compares to actual cash market levels.",
    'wasde_supply_demand': "This chart shows WASDE supply and demand attributes across report dates. Identify: is supply or demand being revised more aggressively, whether the supply/demand balance is tightening or loosening, and what the net balance implies for price direction.",
}


def _call(messages, max_tokens=600):
    headers = {
        'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://agripulse.app',
        'X-Title': 'AgriPulse',
    }
    payload = {
        'model': settings.OPENROUTER_MODEL,
        'messages': messages,
        'temperature': 0.3,
        'max_tokens': max_tokens,
    }
    r = requests.post(URL, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return _strip_markdown(r.json()['choices'][0]['message']['content'])


def generate_module_insight(module, data_summary):
    """3-4 bullet module-level insight. Cached daily."""
    cache_key = f'mod_insight_{module}_{date.today().isoformat()}'
    cached = cache.get(cache_key)
    if cached:
        return cached
    ctx = json.dumps({'module': module, 'as_of': str(date.today()), 'data': data_summary}, default=str)
    prompt = f"{MODULE_PROMPTS.get(module, 'Analyze this agricultural market data.')} Give exactly 4 numbered points. One sentence each. No markdown. No dashes. Numbers only: 1. 2. 3. 4.\n\nData:\n{ctx}"
    try:
        result = _call([
            {'role': 'system', 'content': SYSTEM_BASE},
            {'role': 'user', 'content': prompt},
        ])
        cache.set(cache_key, result, timeout=86400)
        return result
    except Exception as e:
        return f'Insight unavailable: {str(e)}'


def generate_chart_insight(chart_id, chart_data_summary):
    """1-2 sentence insight for a specific chart. Cached daily."""
    cache_key = f'chart_insight_{chart_id}_{date.today().isoformat()}'
    cached = cache.get(cache_key)
    if cached:
        return cached
    prompt_base = CHART_PROMPTS.get(chart_id, 'Analyze this chart data and identify the most important trend or anomaly in 1-2 sentences.')
    ctx = json.dumps(chart_data_summary, default=str)
    prompt = f"{prompt_base}\n\nRespond in exactly 1-2 sentences. Plain text only. No markdown.\n\nData:\n{ctx}"
    try:
        result = _call([
            {'role': 'system', 'content': SYSTEM_BASE},
            {'role': 'user', 'content': prompt},
        ], max_tokens=150)
        cache.set(cache_key, result, timeout=86400)
        return result
    except Exception as e:
        return f'Insight unavailable: {str(e)}'


def ask_chart(chart_id, question, chart_data_summary, history=None):
    """User asks a free-form question about a specific chart."""
    ctx = json.dumps(chart_data_summary, default=str)
    chart_desc = CHART_PROMPTS.get(chart_id, 'agricultural market chart')
    system = f"{SYSTEM_BASE}\n\nYou are answering a question about this specific chart: {chart_desc}\n\nChart data context:\n{ctx}"
    messages = [{'role': 'system', 'content': system}]
    if history:
        for turn in history[-6:]:
            messages.append({'role': turn['role'], 'content': turn['content']})
    messages.append({'role': 'user', 'content': question})
    try:
        return _call(messages, max_tokens=400)
    except Exception as e:
        return f'Could not get response: {str(e)}'


def chat(message, module, context_snapshot, history=None):
    """General chatbot — module-aware."""
    ctx = json.dumps(context_snapshot, default=str)
    system = f"{SYSTEM_BASE}\n\nThe advisor is viewing the {module.replace('_',' ').title()} module.\nCurrent data context:\n{ctx}"
    messages = [{'role': 'system', 'content': system}]
    if history:
        for turn in history[-6:]:
            messages.append({'role': turn['role'], 'content': turn['content']})
    messages.append({'role': 'user', 'content': message})
    try:
        return _call(messages, max_tokens=500)
    except Exception as e:
        return f'Could not get response: {str(e)}'


def generate_cross_signal_insight(all_summaries):
    """Cross-module insight — sees all 5 modules at once. Cached daily."""
    cache_key = f'cross_signal_{date.today().isoformat()}'
    cached = cache.get(cache_key)
    if cached:
        return cached
    ctx = json.dumps(all_summaries, default=str)
    prompt = f"""You have data from all five AgriPulse modules: Slaughter Pace, Cutout Values, Cash vs Futures, LRP Insurance, and WASDE.
Identify 2-3 cross-signal insights that span multiple modules — patterns or contradictions that would not be visible looking at any one module alone.
These are the insights most valuable to advisors. Plain text only. No markdown. Use dashes for bullets.

Full data snapshot:
{ctx}"""
    try:
        result = _call([
            {'role': 'system', 'content': SYSTEM_BASE},
            {'role': 'user', 'content': prompt},
        ], max_tokens=400)
        cache.set(cache_key, result, timeout=86400)
        return result
    except Exception as e:
        return f'Cross-signal insight unavailable: {str(e)}'