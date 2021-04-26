'''
python3 formatchecker.py [-h] [--paper_type {long,short,other}] file_or_dir [file_or_dir ...]
'''

# TODO: make the script pip installable

import argparse
import json
from collections import defaultdict
from os import walk
from os.path import isfile, join
import pdfplumber
from tqdm import tqdm


class Formatter(object):
    def __init__(self):
        self.offset = 2.5

    def format_check(self, submission, paper_type):
        print(f"Checking {submission}")

        self.pdf = pdfplumber.open(submission)
        self.logs = defaultdict(list)  # reset log before calling the format-checking functions
        self.page_errors = set()

        # TODO: A few papers take hours to check. Consider using a timeout
        self.check_page_size()
        self.check_page_margin()
        self.check_page_num(paper_type)
        self.check_font()
        self.check_references()

        output_file = submission.replace(".pdf", "_format.json")
        json.dump(self.logs, open(output_file, 'w'))  # always write a log file even if it is empty
        if self.logs:
            print(f"Errors. Check {output_file} for details.")

    def check_page_size(self):
        '''Checks the paper size (A4) of each pages in the submission.'''

        pages = []
        for i, p in enumerate(self.pdf.pages):
            # TODO: Verify the values used as criteria.
            if (round(p.width), round(p.height)) != (595, 842):
                pages.append(i+1)
        if pages:
            self.logs["SIZE"] += ["Size of page {} is not A4.".format(pages)]
        self.page_errors.update(pages)

    def check_page_margin(self):
        '''Checks if any text or figure is in the margin of pages.'''

        pages_image = set()
        pages_text = defaultdict(list)
        perror = []
        for i, p in enumerate(self.pdf.pages):
            if i+1 in self.page_errors:
                continue
            try:
                # Parse images.
                for image in p.images:
                    if float(image["top"]) < 56 or float(image["x0"]) < 69 or \
                       595-float(image["x1"]) < (69-self.offset):
                        pages_image.add(i+1)

                # Parse texts.
                for j, word in enumerate(p.extract_words()):
                    if float(word["top"]) < 56 or float(word["x0"]) < 69 or \
                       595-float(word["x1"]) < (69-self.offset):
                        pages_text[i+1] += [word["text"], float(word["x0"]), \
                                            595-float(word["x1"])]

                # TODO: do you need to check tables and lines as well?
            except:
                perror.append(i+1)

        if perror:
            self.page_errors.update(perror)
            self.logs["PARSING"] = ["Error occurs when parsing page {}.".format(perror)]
        if pages_image:
            p = sorted(list(pages_image))
            self.logs["MARGIN"] += ["Images on page {} <may> fall in the margin.".format(p)]
        if pages_text:
            p = sorted(pages_text.keys())
            self.logs["MARGIN"] += ["Texts on page {} <may> fall in the margin.".format(p)]
            self.logs["MARGIN"] += ["Details are as follows:", dict(pages_text)]

    def check_page_num(self, paper_type):
        '''Check if the paper exceeds the page limit.'''

        # Set the threshold for different types of paper.
        # TODO: Enable uploading a paper_type file to include all papers' types.
        standards = {"short": 5, "long": 9, "other": float("inf")}
        page_threshold = standards[paper_type.lower()]
        candidates = {"References", "Acknowl", "Ethic", "Broader Impact"}
        acks = {"Acknowledgment", "Acknowledgement"}

        # Find (references, acknowledgements, ethics).
        marker = None
        if len(self.pdf.pages) <= page_threshold:
            return
        for i, p in enumerate(self.pdf.pages):
            if i+1 in self.page_errors:
                continue

            texts = p.extract_text().split('\n')
            for j, line in enumerate(texts):
                if marker is None and any(x in line for x in candidates):
                    marker = (i+1, j+1)
                if "Acknowl" in line and all(x not in line for x in acks):
                    self.logs["MISSPELL"] = ["'Acknowledgments' was misspelled."]

        # if the first marker appears after the first line of page 10,
        # there is high probability the paper exceeds the page limit.
        if marker > (page_threshold + 1, 1):
            page, line = marker
            self.logs["PAGELIMIT"] = [f"Paper <may> exceed the page limit "
                                      f"because first (References, "
                                      f"Acknowledgments, Ethics) was found on "
                                      f"page {page}, line {line}."]

    def check_font(self):
        '''Check the font'''

        correct_fontname = "NimbusRomNo9L-Regu"
        fonts = defaultdict(int)
        for i, page in enumerate(self.pdf.pages):
            try:
                for char in page.chars:
                    fonts[char['fontname']] += 1
            except:
                self.logs["FONT"] += [f"Can't parse page #{i}"]
        max_font_count, max_font_name = max((count, name) for name, count in fonts.items())  # find most used font
        sum_char_count = sum(fonts.values())
        if max_font_count / sum_char_count < 0.35:  # the most used font should be used more than 35% of the time
            self.logs["FONT"] += ["Can't find the main font"]

        if not max_font_name.endswith(correct_fontname):  # the most used font should be `correct_fontname`
            self.logs["FONT"] += [f"Wrong font. The main font used is {max_font_name} when it should be {correct_fontname}."]

    def check_references(self):
        '''Check that citations have URLs, and that they have venues (not just arXiv ids)'''

        found_references = False
        arxiv_word_count = 0
        doi_url_count = 0
        arxiv_url_count = 0
        all_url_count = 0

        for i, page in enumerate(self.pdf.pages):
            try:
                page_text = page.extract_text()
            except:
                page_text = ""
                self.logs["BIB"] += [f"Can't parse page #{i}"]

            lines = page_text.split('\n')
            for j, line in enumerate(lines):
                if "References" in line:
                    found_references = True
                    break
            if found_references:
                arxiv_word_count += page_text.lower().count('arxiv')
                urls = [h['uri'] for h in page.hyperlinks]
                urls = set(urls)  # When link text spans more than one line, it returns the same url multiple times
                for url in urls:
                    if 'doi.org' in url:
                        doi_url_count += 1
                    elif 'arxiv.org' in url:
                        arxiv_url_count += 1
                    all_url_count += 1

        # The following checks fail in ~60% of the papers. TODO: relax them a bit

        if doi_url_count < 3:
            self.logs["BIB"] += [f"Bibliography should use ACL Anothology DOIs whenever possible. Only {doi_url_count} references do."]

        if arxiv_url_count > 0.2 * all_url_count:  # only 20% of the links are allowed to be arXiv links
            self.logs["BIB"] += [f"It appears you are using arXiv links more than you should ({arxiv_url_count}/{all_url_count}). Consider using ACL Anothology DOIs instead."]

        if all_url_count < 5:
            self.logs["BIB"] += [f"It appears most of the references are not using paper links. Only {all_url_count} links found."]

        if arxiv_word_count > 10:
            self.logs["BIB"] += [f"It appears you are using arXiv references more than you should ({arxiv_word_count} found). Consider using ACL Anothology references instead."]

        if not found_references:
            self.logs["BIB"] += ["Couldn't find references"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('submission_paths', metavar='file_or_dir', nargs='+',
                        default=[])
    parser.add_argument('--paper_type', choices={"short", "long", "other"},
                        default='long')
    parser.add_argument('--num_workers', type=int, default=1)
    
    args = parser.parse_args()

    # retrieve file paths
    paths = {join(root, file_name)
             for path in args.submission_paths
             for root, _, file_names in walk(path)
             for file_name in file_names}
    paths.update(args.submission_paths)

    # retrive files
    fileset = sorted([p for p in paths if isfile(p) and p.endswith(".pdf")])

    if not fileset:
        print(f"No PDF files found in {paths}")

    def worker(pdf_path):
        """ process one pdf """
        Formatter().format_check(submission=pdf_path, paper_type=args.paper_type)
        
    if args.num_workers > 1:
        from multiprocessing.pool import Pool
        with Pool(args.num_workers) as p:
            list(tqdm(p.imap(worker, fileset), total=len(fileset)))
    else:
        for submission in tqdm(fileset):
            worker(submission)

if __name__ == "__main__":
    main()

