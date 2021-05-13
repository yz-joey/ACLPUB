import argparse
import collections
import datetime
import logging
import sys
import time

import googletools


def hh_mm(text):
    try:
        result = time.strptime(text, "%I:%M%p")
    except ValueError:
        result = time.strptime(text, "%I%p")
    return time.strftime("%H:%M", result)


def sheet_to_order(spreadsheet_id, sessions_range, papers_range, start_date):
    # collect the session and paper information from the Google sheet
    values = googletools.sheets_service().spreadsheets().values()
    sessions_rows = values.get(spreadsheetId=spreadsheet_id,
                               range=sessions_range).execute()["values"]
    papers_rows = values.get(spreadsheetId=spreadsheet_id,
                             range=papers_range).execute()["values"]

    # group papers by block+session
    session_to_papers = collections.defaultdict(list)
    for row in papers_rows[1:]:
        try:
            [submission_id,
             authors,
             title,
             track,
             acceptance_status,
             main_contact_country,
             subject_area,
             submission_type,
             group,
             block,
             session,
             date_and_time] = row

            # strip emails from author list (only included in TACL entries)
            if 'TACL' in submission_id:
                authors = ", ".join(
                    author_email.rsplit(maxsplit=1)[0].rstrip(":,")
                    for author_email in authors.split("; "))

            # map block+session to paper info
            paper = submission_id, authors, title, group
            session_to_papers[block, session].append(paper)
        except ValueError:
            logging.warning(f"Invalid row: {row}")

    # assemble the order file
    order_lines = []
    old_day_name = None
    start_date -= datetime.timedelta(days=start_date.weekday())
    for row in sessions_rows[1:]:
        [block,
         session,
         date_and_time,
         friendly_time_zones,
         session_title] = row

        # calculate the date and time of this session
        day_name, time_frame = date_and_time.split(", ")
        start_time, end_time = [hh_mm(t) for t in time_frame.split("-")]

        # if it's a new day, add a day entry
        if day_name != old_day_name:
            day_number = time.strptime(day_name, "%A").tm_wday
            date = start_date + datetime.timedelta(days=day_number)
            order_lines.append(date.strftime("* %a %d %b %Y (all times PST)"))
            old_day_name = day_name

        # add a session entry
        order_lines.append(f"= {start_time}--{end_time} {session_title}")

        # add an entry for each paper
        papers = session_to_papers.pop((block, session))
        for submission_id, authors, title, _ in papers:
            # for regular papers, add them by submission number
            if submission_id.isdigit():
                order_lines.append(f"{submission_id} # {title}")
            else:
                order_lines.append(f"! [{submission_id}] {title} %by {authors}")

    # make sure all papers have been used
    if session_to_papers:
        logging.warning(f"unused papers: {session_to_papers}")

    # return the constructed order file
    return "\n".join(order_lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--spreadsheet-id',
                        default='14ebEFK6egReR2Y_6BxdMO6V_LZoOMhqk1OGYNUYpLI0')
    parser.add_argument('--papers-range', default='Final-AllPaperTimes!A:L')
    parser.add_argument('--sessions-range', default='Detailed Schedule!A:E')
    parser.add_argument('--start-date', type=datetime.date.fromisoformat,
                        default="2021-06-07")
    args = parser.parse_args()
    with open("order.txt", "w") as order_file:
        order_file.write(sheet_to_order(**vars(args)))
