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


def check_metadata(
        submissions_path,
        pdfs_dir,
        spreadsheet_id,
        sheet_id,
        id_column,
        problem_column,
        post=False):

    # map submission IDs to PDF paths
    id_to_pdf = {}
    for root, _, filenames in os.walk(pdfs_dir):
        for filename in filenames:
            if filename.endswith("_Paper.pdf"):
                submission_id, _ = filename.split("_", 1)
                id_to_pdf[int(submission_id)] = os.path.join(root, filename)

    problems = collections.defaultdict(list)
    row_to_problem = {}

    df = pd.read_csv(submissions_path, keep_default_na=False)
    for index, row in df.iterrows():
        submission_id = row["Submission ID"]

        # open the PDF
        pdf_path = id_to_pdf[submission_id]
        pdf = pdfplumber.open(pdf_path)

        # assumes metadata can be found in the first 500 characters
        text = _clean_str(pdf.pages[0].extract_text()[:500])

        # collect all authors and their affiliations
        names = []
        for i in range(1, 25):
            for x in ['First', 'Middle', 'Last']:
                name_part = _clean_str(row[f'{i}: {x} Name'])
                if name_part:
                    names.extend(name_part.split())

        # check for author names in the expected order, allowing for
        # punctuation, affiliations, etc. between names
        # NOTE: only removed or re-ordered (not added) authors will be caught
        match = re.search('.*?'.join(names), text, re.DOTALL)
        if not match:

            # check if there is a match when ignoring case, punctuation, accents
            # since this is the most common type of error
            allowed_chars = r'[\p{Zs}\p{p}\p{Mn}]'
            match_ignoring_case_punct_accent = re.search(
                '.*?'.join(
                    fr'{allowed_chars}*'.join(unidecode.unidecode(c) for c in p)
                    for part in names for p in re.split(allowed_chars, part)),
                unidecode.unidecode(text),
                re.DOTALL | re.IGNORECASE)
            if match_ignoring_case_punct_accent:
                problem = 'CASE-PUNCT-ACCENT'
                # these offsets may be slightly incorrect because unidecode may
                # change the number of characters, but it should be close enough
                start, end = match_ignoring_case_punct_accent.span()
                in_text = text[start: end]
            else:
                problem = 'UNKNOWN'
                in_text = text

            # format the problem both for stdout and for the spreadsheet
            comparison_text = f"meta=\"{' '.join(names)}\"\npdf =\"{in_text}\""
            problems[problem].append(f"{submission_id}:\n{comparison_text}\n")

            # row in the spreadsheet is 1-based and first row is the header
            row_to_problem[index + 2] = f"{problem}:\n{comparison_text}"

    # print all problems, grouped by type of problem
    for problem_type in sorted(problems):
        print(problem_type)
        for problem_text in problems[problem_type]:
            print(problem_text)

    # report overall problem statistics
    total_problems = sum(len(texts) for texts in problems.values())
    print(f"{total_problems} submissions failed:")
    for problem_type in sorted(problems):
        print(f"  {len(problems[problem_type])} {problem_type}")

    # if requested, post problems to the Google Sheet
    if post:
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
    check_metadata(**vars(args))
