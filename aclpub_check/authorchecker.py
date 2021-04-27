import argparse
import collections
import os
import os.path
import regex as re
import unicodedata

import pandas as pd
import pdfplumber
import unidecode

import googletools


def _clean_str(value):
    if pd.isna(value):
        return ''
    # not exactly sure why, but this has to be done iteratively
    old_value = None
    value = value.strip()
    while old_value != value:
        old_value = value
        # strip space before accent; PDF seems to introduce these
        value = re.sub(r'\p{Zs}+(\p{Mn})', r'\1', value)
        # combine accents with characters
        value = unicodedata.normalize('NFKC', value)
    return value


def _strip_punct_accent(text):
    return re.sub(r'\p{P}', '', unidecode.unidecode(text))


def check_authors(
        submissions_path,
        pdfs_dir,
        spreadsheet_id,
        sheet_id,
        id_column,
        problem_column,
        post=False):
    df = pd.read_csv(submissions_path, keep_default_na=False)
    id_to_names = {}
    id_to_row = {}
    for index, row in df.iterrows():
        submission_id = row["Submission ID"]
        id_to_row[submission_id] = index + 2

        # collect all authors and their affiliations
        id_to_names[submission_id] = []
        for i in range(1, 25):
            for x in ['First', 'Middle', 'Last']:
                name_part = _clean_str(row[f'{i}: {x} Name'])
                if name_part:
                    id_to_names[submission_id].extend(name_part.split())

    papers = []
    for root, _, filenames in os.walk(pdfs_dir):
        for filename in filenames:
            if filename.endswith("_Paper.pdf"):
                submission_id, _ = filename.split("_", 1)
                papers.append((int(submission_id), os.path.join(root, filename)))

    problems = collections.defaultdict(list)
    row_to_problem = {}
    for submission_id, pdf_path in sorted(papers):
        names = id_to_names[submission_id]
        pdf = pdfplumber.open(pdf_path)
        first_text = pdf.pages[0].extract_text()[:500]
        text = _clean_str(first_text)
        match = re.search('.*?'.join(names), text, re.DOTALL)
        if not match:
            no_case_no_punct_no_accent_match = re.search(
                '.*?'.join(_strip_punct_accent(n) for n in names),
                _strip_punct_accent(text), re.DOTALL | re.IGNORECASE)
            if no_case_no_punct_no_accent_match:
                problem = 'CASE-PUNCT-ACCENT'
                in_text = no_case_no_punct_no_accent_match.group()
            else:
                problem = 'UNKNOWN'
                in_text = text
            comparison_text = f"meta=\"{' '.join(names)}\"\npdf =\"{in_text}\""
            problems[problem].append(f"{submission_id}:\n{comparison_text}\n")
            row = id_to_row[submission_id]
            row_to_problem[row] = f"{problem}:\n{comparison_text}"

    for problem_type in sorted(problems):
        print(problem_type)
        for problem_text in problems[problem_type]:
            print(problem_text)

    total_problems = sum(len(texts) for texts in problems.values())
    print(f"{total_problems} submissions failed:")
    for problem_type in sorted(problems):
        print(f"  {len(problems[problem_type])} {problem_type}")

    if post:
        # open up the Google Sheet
        values = googletools.sheets_service().spreadsheets().values()

        # get the number of rows
        id_range = f'{sheet_id}!{id_column}1:{id_column}'
        request = values.get(spreadsheetId=spreadsheet_id, range=id_range)
        n_rows = len(request.execute()['values'])

        # fill in the problem column
        request = values.update(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_id}!{problem_column}2:{problem_column}',
            valueInputOption='RAW',
            body={'values': [[row_to_problem.get(i, '')]
                             for i in range(2, n_rows)]})
        request.execute()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--submissions', dest='submissions_path',
                        default='Submission_Information.csv')
    parser.add_argument('--pdfs', dest='pdfs_dir', default='final')
    parser.add_argument('--post', action='store_true')
    parser.add_argument('--spreadsheet-id',
                        default='1lQyGZNBEBwukf8-mgPzIH57xUX9y4o2OUCzpEvNpW9A')
    parser.add_argument('--sheet-id', default='Sheet1')
    parser.add_argument('--id-column', default='A')
    parser.add_argument('--problem-column', default='F')
    args = parser.parse_args()
    check_authors(**vars(args))
