import pandas as pd
import numpy as np
from core.services import data_loader as dl
from core.services import ai_engine as ai


# Metric weights for similarity scoring
WEIGHTS = {
    'week_of_year':    0.30,
    'choice_cutout':   0.25,
    'carcass_weight':  0.20,
    'spread':          0.15,
    'cash_price':      0.10,
}


def _normalize(series):
    """Min-max normalize a series to 0-1."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - mn) / (mx - mn)


def find_comparable_weeks(target_week=None, n=3):
    """
    Find the n most similar historical weeks to the target week.
    Returns list of dicts with match metadata and outcome.
    """
    matrix = dl.get_comparable_week_matrix()
    if matrix.empty:
        return []

    matrix['week'] = pd.to_datetime(matrix['week'])
    matrix = matrix.dropna(subset=['choice_cutout', 'carcass_weight'])

    # Default to latest week
    if target_week is None:
        target_week = matrix['week'].max()
    else:
        target_week = pd.to_datetime(target_week)

    # Get target row
    target = matrix[matrix['week'] == target_week]
    if target.empty:
        # Find nearest week
        idx = (matrix['week'] - target_week).abs().idxmin()
        target = matrix.loc[[idx]]
        target_week = matrix.loc[idx, 'week']

    target_row = target.iloc[0]

    # Exclude current year from candidates to avoid trivial matches
    # Also exclude weeks within 8 weeks of target to avoid near-matches
    candidates = matrix[
        (matrix['week'] < target_week - pd.Timedelta(weeks=8)) &
        (matrix['year'] < target_row['year'])
    ].copy()

    if len(candidates) < n:
        candidates = matrix[matrix['week'] < target_week - pd.Timedelta(weeks=8)].copy()

    if candidates.empty:
        return []

    # Normalize all metrics across the full dataset for consistent scaling
    all_data = matrix.copy()
    for col in ['week_of_year', 'choice_cutout', 'carcass_weight', 'spread', 'cash_price']:
        if col in all_data.columns:
            all_data[col + '_norm'] = _normalize(all_data[col].fillna(all_data[col].median()))

    # Get target normalized values
    target_norms = {}
    for col in WEIGHTS.keys():
        norm_col = col + '_norm'
        if norm_col in all_data.columns:
            target_idx = all_data[all_data['week'] == target_week].index
            if len(target_idx) > 0:
                target_norms[col] = all_data.loc[target_idx[0], norm_col]
            else:
                target_norms[col] = 0.5

    # Compute weighted Euclidean distance for each candidate
    candidate_indices = candidates.index.tolist()
    distances = []
    for idx in candidate_indices:
        row = all_data.loc[idx]
        dist = 0
        for col, weight in WEIGHTS.items():
            norm_col = col + '_norm'
            if norm_col in all_data.columns and col in target_norms:
                val = row.get(norm_col, 0.5)
                diff = (val - target_norms[col]) ** 2
                dist += weight * diff
        distances.append((idx, np.sqrt(dist)))

    distances.sort(key=lambda x: x[1])
    top_matches = distances[:n]

    results = []
    for idx, dist in top_matches:
        match_row = matrix.loc[idx]
        match_week = match_row['week']

        # Similarity score (0-100, higher = more similar)
        similarity = max(0, round((1 - dist) * 100, 1))

        # Get outcome: what happened in the 4 weeks after this match
        outcome = dl.get_week_outcome(match_week.date())
        outcome_summary = _summarize_outcome(outcome, match_row)

        results.append({
            'week': match_week.strftime('%b %d, %Y'),
            'week_date': match_week.isoformat(),
            'year': int(match_row['year']),
            'similarity': similarity,
            'metrics': {
                'choice_cutout': f"${match_row['choice_cutout']:.2f}" if pd.notna(match_row.get('choice_cutout')) else 'N/A',
                'select_cutout': f"${match_row['select_cutout']:.2f}" if pd.notna(match_row.get('select_cutout')) else 'N/A',
                'spread': f"${match_row['spread']:.2f}" if pd.notna(match_row.get('spread')) else 'N/A',
                'carcass_weight': f"{match_row['carcass_weight']:.1f} lbs" if pd.notna(match_row.get('carcass_weight')) else 'N/A',
                'cash_price': f"${match_row['cash_price']:.2f}" if pd.notna(match_row.get('cash_price')) else 'N/A',
                'week_of_year': int(match_row['week_of_year']),
            },
            'outcome': outcome_summary,
            'distance': round(dist, 4),
        })

    return results


def _summarize_outcome(outcome_df, match_row):
    """Summarize what happened in the 4 weeks after the matched week."""
    if outcome_df.empty:
        return {'summary': 'No outcome data available for this period.', 'cutout_change': None, 'cash_change': None}

    try:
        first_cutout = outcome_df['choice_cutout'].dropna().iloc[0] if not outcome_df['choice_cutout'].dropna().empty else None
        last_cutout = outcome_df['choice_cutout'].dropna().iloc[-1] if not outcome_df['choice_cutout'].dropna().empty else None
        first_cash = outcome_df['cash_price'].dropna().iloc[0] if not outcome_df['cash_price'].dropna().empty else None
        last_cash = outcome_df['cash_price'].dropna().iloc[-1] if not outcome_df['cash_price'].dropna().empty else None

        cutout_change = None
        cash_change = None
        parts = []

        if first_cutout and last_cutout and first_cutout > 0:
            cutout_change = round(((last_cutout - first_cutout) / first_cutout) * 100, 1)
            direction = 'rose' if cutout_change > 0 else 'fell'
            parts.append(f"Choice cutout {direction} {abs(cutout_change):.1f}% over the next 4 weeks (${first_cutout:.2f} to ${last_cutout:.2f})")

        if first_cash and last_cash and first_cash > 0:
            cash_change = round(((last_cash - first_cash) / first_cash) * 100, 1)
            direction = 'strengthened' if cash_change > 0 else 'weakened'
            parts.append(f"cash prices {direction} {abs(cash_change):.1f}% (${first_cash:.2f} to ${last_cash:.2f})")

        summary = '. '.join(parts) + '.' if parts else 'Limited price data available for this period.'

        return {
            'summary': summary,
            'cutout_change': cutout_change,
            'cash_change': cash_change,
        }
    except Exception:
        return {'summary': 'Outcome data could not be computed.', 'cutout_change': None, 'cash_change': None}


def get_ai_comparable_insight(target_metrics, matches):
    """Generate AI insight comparing current week to historical analogs."""
    from django.core.cache import cache
    import json
    from datetime import date

    cache_key = f"comparable_insight_{matches[0]['week_date'] if matches else 'none'}_{date.today().isoformat()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    context = {
        'current_week_metrics': target_metrics,
        'historical_matches': [
            {
                'week': m['week'],
                'similarity': m['similarity'],
                'metrics': m['metrics'],
                'outcome': m['outcome'],
            } for m in matches
        ]
    }

    species = 'hog' if 'pork_carcass' in str(target_metrics) or 'hog_carcass' in str(target_metrics) else 'cattle'
    price_term = 'pork/hog prices' if species == 'hog' else 'beef/cattle prices'
    data_depth = '2013' if species == 'hog' else '2004'

    prompt = f"""You are analyzing historical market analogs for livestock advisors.

The current week's {species} market metrics are compared to the 3 most similar historical weeks found in data going back to {data_depth}.

For each historical match, the data shows what actually happened in the 4 weeks that followed.

Based on these analogs:
1. What do the historical outcomes suggest about the likely direction for {price_term} over the next 4 weeks?
2. Are the historical outcomes consistent or do they conflict — and what does that imply about confidence level?
3. What is the single most actionable insight an advisor should take from these analogs?

Give exactly 3 numbered points. Plain text only. No markdown. One sentence each.

Data:
{json.dumps(context, default=str)}"""

    try:
        result = ai._call([
            {'role': 'system', 'content': ai.SYSTEM_BASE},
            {'role': 'user', 'content': prompt},
        ], max_tokens=300)
        cache.set(cache_key, result, timeout=86400)
        return result
    except Exception as e:
        return f'Analog insight unavailable: {str(e)}'


# HOG WEIGHTS
HOG_WEIGHTS = {
    'week_of_year':       0.30,
    'pork_carcass':       0.25,
    'hog_carcass_weight': 0.20,
    'belly_value':        0.15,
    'cash_hog_price':     0.10,
}


def find_comparable_weeks_hogs(target_week=None, n=3):
    """Find n most similar historical hog market weeks."""
    matrix = dl.get_hog_comparable_matrix()
    if matrix.empty:
        return []

    matrix['week'] = pd.to_datetime(matrix['week'])
    matrix = matrix.dropna(subset=['pork_carcass', 'hog_carcass_weight'])

    if target_week is None:
        target_week = matrix['week'].max()
    else:
        target_week = pd.to_datetime(target_week)

    target = matrix[matrix['week'] == target_week]
    if target.empty:
        idx = (matrix['week'] - target_week).abs().idxmin()
        target = matrix.loc[[idx]]
        target_week = matrix.loc[idx, 'week']

    target_row = target.iloc[0]

    candidates = matrix[
        (matrix['week'] < target_week - pd.Timedelta(weeks=8)) &
        (matrix['year'] < target_row['year'])
    ].copy()

    if len(candidates) < n:
        candidates = matrix[matrix['week'] < target_week - pd.Timedelta(weeks=8)].copy()

    if candidates.empty:
        return []

    all_data = matrix.copy()
    for col in HOG_WEIGHTS.keys():
        if col in all_data.columns:
            all_data[col + '_norm'] = _normalize(all_data[col].fillna(all_data[col].median()))

    target_norms = {}
    for col in HOG_WEIGHTS.keys():
        norm_col = col + '_norm'
        if norm_col in all_data.columns:
            target_idx = all_data[all_data['week'] == target_week].index
            if len(target_idx) > 0:
                target_norms[col] = all_data.loc[target_idx[0], norm_col]
            else:
                target_norms[col] = 0.5

    distances = []
    for idx in candidates.index.tolist():
        row = all_data.loc[idx]
        dist = 0
        for col, weight in HOG_WEIGHTS.items():
            norm_col = col + '_norm'
            if norm_col in all_data.columns and col in target_norms:
                diff = (row.get(norm_col, 0.5) - target_norms[col]) ** 2
                dist += weight * diff
        distances.append((idx, np.sqrt(dist)))

    distances.sort(key=lambda x: x[1])
    results = []

    for idx, dist in distances[:n]:
        match_row = matrix.loc[idx]
        match_week = match_row['week']
        similarity = max(0, round((1 - dist) * 100, 1))
        outcome = dl.get_hog_week_outcome(match_week.date())
        outcome_summary = _summarize_hog_outcome(outcome)

        results.append({
            'week': match_week.strftime('%b %d, %Y'),
            'week_date': match_week.isoformat(),
            'year': int(match_row['year']),
            'similarity': similarity,
            'metrics': {
                'pork_carcass': f"${match_row['pork_carcass']:.2f}" if pd.notna(match_row.get('pork_carcass')) else 'N/A',
                'belly_value': f"${match_row['belly_value']:.2f}" if pd.notna(match_row.get('belly_value')) else 'N/A',
                'hog_carcass_weight': f"{match_row['hog_carcass_weight']:.1f} lbs" if pd.notna(match_row.get('hog_carcass_weight')) else 'N/A',
                'cash_hog_price': f"${match_row['cash_hog_price']:.2f}" if pd.notna(match_row.get('cash_hog_price')) else 'N/A',
                'week_of_year': int(match_row['week_of_year']),
            },
            'outcome': outcome_summary,
        })

    return results


def _summarize_hog_outcome(outcome_df):
    if outcome_df.empty:
        return {'summary': 'No outcome data available.', 'cutout_change': None, 'cash_change': None}
    try:
        first_c = outcome_df['pork_carcass'].dropna().iloc[0] if not outcome_df['pork_carcass'].dropna().empty else None
        last_c = outcome_df['pork_carcass'].dropna().iloc[-1] if not outcome_df['pork_carcass'].dropna().empty else None
        first_p = outcome_df['cash_price'].dropna().iloc[0] if not outcome_df['cash_price'].dropna().empty else None
        last_p = outcome_df['cash_price'].dropna().iloc[-1] if not outcome_df['cash_price'].dropna().empty else None

        parts = []
        cutout_change = None
        cash_change = None

        if first_c and last_c and first_c > 0:
            cutout_change = round(((last_c - first_c) / first_c) * 100, 1)
            direction = 'rose' if cutout_change > 0 else 'fell'
            parts.append(f"Pork carcass value {direction} {abs(cutout_change):.1f}% (${first_c:.2f} to ${last_c:.2f})")

        if first_p and last_p and first_p > 0:
            cash_change = round(((last_p - first_p) / first_p) * 100, 1)
            direction = 'strengthened' if cash_change > 0 else 'weakened'
            parts.append(f"cash hog prices {direction} {abs(cash_change):.1f}%")

        summary = '. '.join(parts) + '.' if parts else 'Limited price data for this period.'
        return {'summary': summary, 'cutout_change': cutout_change, 'cash_change': cash_change}
    except Exception:
        return {'summary': 'Outcome could not be computed.', 'cutout_change': None, 'cash_change': None}


def get_hog_target_metrics(matrix, target_week=None):
    """Get current week hog metrics for display."""
    if matrix.empty:
        return {}
    matrix = matrix.copy()
    matrix['week'] = pd.to_datetime(matrix['week'])
    if target_week:
        target_week_dt = pd.to_datetime(target_week)
        row = matrix[matrix['week'] == target_week_dt]
        if row.empty:
            idx = (matrix['week'] - target_week_dt).abs().idxmin()
            latest = matrix.loc[idx]
        else:
            latest = row.iloc[0]
    else:
        latest = matrix.sort_values('week').iloc[-1]
    return {
        'week': latest['week'].strftime('%b %d, %Y'),
        'pork_carcass': f"${latest['pork_carcass']:.2f}" if pd.notna(latest.get('pork_carcass')) else 'N/A',
        'belly_value': f"${latest['belly_value']:.2f}" if pd.notna(latest.get('belly_value')) else 'N/A',
        'hog_carcass_weight': f"{latest['hog_carcass_weight']:.1f} lbs" if pd.notna(latest.get('hog_carcass_weight')) else 'N/A',
        'cash_hog_price': f"${latest['cash_hog_price']:.2f}" if pd.notna(latest.get('cash_hog_price')) else 'N/A',
        'week_of_year': int(latest['week_of_year']),
    }
