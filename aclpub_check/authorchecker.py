import argparse
import os
import os.path
import re
import unicodedata

import pandas as pd
import pdfplumber


def _clean_str(value):
    return '' if pd.isna(value) else unicodedata.normalize('NFKC', value.strip())


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

    failures = 0
    for submission_id, pdf_path in sorted(papers):
        names = id_to_names[submission_id]
        pdf = pdfplumber.open(pdf_path)
        text = _clean_str(pdf.pages[0].extract_text())[:500]
        match = re.search('.*?'.join(names), text, re.DOTALL)
        if not match:
            failures += 1
            print(f"{submission_id}: FAILED. can't find \"{';'.join(names)}\" in \"{text}\"\n")

    print(f"{failures} submissions failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--submissions', dest='submissions_path',
                        default='Submission_Information.csv')
    parser.add_argument('--pdfs', dest='pdfs_dir', default='final')
    args = parser.parse_args()
    check_authors(**vars(args))
