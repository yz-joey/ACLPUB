import argparse
import textwrap
import pandas as pd
import googletools


def yield_problems(signature, org_name, org_address):
    if not signature:
        yield "The signature is missing."
    elif signature == "NA":
        yield f'The signature "{signature}" must be accompanied by a ' \
              f'"License to Publish" or equivalent.'
    elif len(signature) < 3 or len(signature.split()) < 2:
        yield f'The signature "{signature}" does not appear to be a full name.'
    if not org_name:
        yield "The organization name is missing."
    elif len(org_name) < 5 and org_name not in {'IBM'}:
        yield f'The organization name "{org_name}" does not appear to be a ' \
              f'full name. '
    if not org_address:
        yield "The organization address is missing."
    elif len(org_address) < 3 or len(org_address.split()) < 2:
        org_address_simple = org_address.replace("\n", " ")
        yield f'The organization address "{org_address_simple}" does not ' \
              f'appear to be a complete physical address. '


def write_copyright_signatures(
        submissions_path,
        spreadsheet_id,
        sheet_id,
        id_column,
        problem_column,
        post=False):

    def clean_str(value):
        return '' if pd.isna(value) else value.strip()

    # write all copyright signatures to a single file, noting any problems
    id_problems = []
    row_to_problems = {}
    with open("copyright-signatures.txt", "w") as output_file:
        df = pd.read_csv(submissions_path, keep_default_na=False)
        for index, row in df.iterrows():
            submission_id = row["Submission ID"]

            # NOTE: These were the names in the custom final submission form
            # for NAACL 2021. Names and structure may be different depending
            # on your final submission form.
            signature = clean_str(row["copyrightSig"])
            org_name = clean_str(row["orgName"])
            org_address = clean_str(row["orgAddress"])

            # check for common copyright signature problems
            problems = list(yield_problems(signature, org_name, org_address))

            # if there were problems, save them to be logged later
            if problems:
                problems_text = "\n".join(problems)
                id_problems.append((submission_id, problems_text))
                row_to_problems[index + 2] = problems_text

            # collect all authors and their affiliations
            authors_parts = []
            for i in range(1, 25):
                name_parts = [
                    clean_str(row[f'{i}: {x} Name'])
                    for x in ['First', 'Middle', 'Last']]
                name = ' '.join(x for x in name_parts if x)
                if name:
                    affiliation = clean_str(row[f"{i}: Affiliation"])
                    authors_parts.append(f'{name} ({affiliation})')
            authors = '\n'.join(authors_parts)

            # write out the copyright signature in the standard ACL format
            indent = " " * 4
            output_file.write(f"""
Submission # {submission_id}
Title: {row["Title"]}
Authors:
{textwrap.indent(authors, indent)}
Signature: {signature}
Your job title (if not one of the authors): {clean_str(row["jobTitle"])}
Name and address of your organization:
{textwrap.indent(org_name, indent)}
{textwrap.indent(org_address, indent)}

=================================================================
""")

    if id_problems:
        # log all problems to the console
        print(f"WARNING: problems logged for {len(id_problems)} submissions:")
        for submission_id, problems_text in id_problems:
            print(f"{submission_id}: {problems_text}")

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
                body={'values': [[row_to_problems.get(i, '')]
                                 for i in range(2, n_rows)]})
            request.execute()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--submissions', dest='submissions_path',
                        default='Submission_Information.csv')
    parser.add_argument('--post', action='store_true')
    parser.add_argument('--spreadsheet-id',
                        default='1lQyGZNBEBwukf8-mgPzIH57xUX9y4o2OUCzpEvNpW9A')
    parser.add_argument('--sheet-id', default='Sheet1')
    parser.add_argument('--id-column', default='A')
    parser.add_argument('--problem-column', default='E')
    args = parser.parse_args()
    write_copyright_signatures(**vars(args))
