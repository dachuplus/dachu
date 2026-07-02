"""
Count how many fund_combined rows (score_grade IS NULL, t0 != '货币型')
have corresponding scores in fund_scores (k_all is not null).
Uses Supabase REST API with anon key.
"""

import requests

SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co'
ANON_KEY = 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'

HEADERS = {
    'apikey': ANON_KEY,
    'Authorization': f'Bearer {ANON_KEY}',
}

BATCH_SIZE = 100


def supabase_get(table, params):
    url = f'{SUPABASE_URL}/rest/v1/{table}'
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    # Step 1: Fetch all fund_combined where score_grade IS NULL; filter t0 != 货币型 in Python
    print('Fetching fund_combined (score_grade IS NULL)...')
    candidates = []
    offset = 0
    page_size = 1000
    while True:
        params = {
            'select': 'c,t0',
            'score_grade': 'is.null',
            'order': 'c',
            'offset': offset,
            'limit': page_size,
        }
        page = supabase_get('fund_combined', params)
        if not page:
            break
        for row in page:
            if row.get('t0') != '货币型':
                candidates.append(row['c'])
        offset += page_size
        if len(page) < page_size:
            break

    total = len(candidates)
    print(f'Total candidates (null score_grade, non-货币型): {total}')

    if total == 0:
        print('No candidates found.')
        return

    # Step 2: Batch-check fund_scores with '.OF' suffix for k_all
    have_scores = 0
    no_scores = 0
    total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, total, BATCH_SIZE):
        batch = candidates[i:i + BATCH_SIZE]
        batch_codes = [f'{c}.OF' for c in batch]
        code_list = ','.join(batch_codes)

        params = {
            'select': 'c',
            'c': f'in.({code_list})',
            'k_all': 'not.is.null',
            'limit': BATCH_SIZE + 1,
        }

        try:
            results = supabase_get('fund_scores', params)
            found_codes = set(r['c'] for r in results)
        except Exception as e:
            batch_num = i // BATCH_SIZE + 1
            print(f'  Batch {batch_num}/{total_batches} error: {e}')
            found_codes = set()

        for code in batch:
            if f'{code}.OF' in found_codes:
                have_scores += 1
            else:
                no_scores += 1

        batch_num = i // BATCH_SIZE + 1
        print(f'Batch {batch_num}/{total_batches}: have={have_scores}, no={no_scores}')

    # Step 3: Report
    print()
    print('=' * 50)
    print('RESULTS')
    print('=' * 50)
    print(f'Total null score_grade non-货币型: {total}')
    print(f'Have scores (k_all) in fund_scores: {have_scores}')
    print(f'No scores in fund_scores:            {no_scores}')
    print('=' * 50)


if __name__ == '__main__':
    main()
