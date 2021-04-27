import argparse
import collections
import os
import os.path
import regex as re
import unicodedata

import pandas as pd
import pdfplumber
import unidecode


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


def check_authors(submissions_path, pdfs_dir):
    df = pd.read_csv(submissions_path, keep_default_na=False)
    id_to_names = {}
    for index, row in df.iterrows():
        submission_id = row["Submission ID"]

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
            problems[problem].append(f"{submission_id}:\n"
                                     f"meta=\"{' '.join(names)}\"\n"
                                     f"pdf =\"{in_text}\"\n")

    for problem_type in sorted(problems):
        print(problem_type)
        for problem_text in problems[problem_type]:
            print(problem_text)

    total_problems = sum(len(texts) for texts in problems.values())
    print(f"{total_problems} submissions failed:")
    for problem_type in sorted(problems):
        print(f"  {len(problems[problem_type])} {problem_type}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--submissions', dest='submissions_path',
                        default='Submission_Information.csv')
    parser.add_argument('--pdfs', dest='pdfs_dir', default='final')
    args = parser.parse_args()
    check_authors(**vars(args))
