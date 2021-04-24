'''
python3 formatchecker.py [-h] [--paper_type {long,short,other}] file_or_dir [file_or_dir ...]
'''

import argparse
import json
import pdfplumber

from collections import defaultdict
from os import walk
from os.path import isfile, join, exists
from tqdm import tqdm


class Formatter(object):
    def __init__(self):
        self.offset = 2.5

    def format_check(self, submission_paths, paper_type):
        paths = {join(root, file_name)
                 for path in submission_paths
                 for root, _, file_names in walk(path)
                 for file_name in file_names}
        paths.update(submission_paths)
        fileset = {p for p in paths if isfile(p) and p.endswith(".pdf")}
        if not fileset:
            print(f"No PDF files found in {paths}"); return
        for submission in tqdm(sorted(list(fileset))):
            self.pdf = pdfplumber.open(submission)
            self.logs = defaultdict(list)  # reset log before calling the format-checking functions
            self.page_errors = set()
            self.page_size(); self.page_margin(); self.page_num(paper_type)
            if self.logs:
                output_file = submission.replace(".pdf", "_format.json")
                json.dump(self.logs, open(output_file, 'w'))
                print("Finished. Details shown in {}.".format(output_file))
            else:
                print("Finished. {} is in good shape.".format(submission))

    def page_size(self):
        '''Checks the paper size (A4) of each pages in the submission.'''

        pages = []
        for i,p in enumerate(self.pdf.pages):
            if (round(p.width), round(p.height)) != (595, 842):
                pages.append(i+1)
        if pages:
            self.logs["SIZE"] += ["Size of page {} is not A4.".format(pages)]
        self.page_errors.update(pages)
        
    def page_margin(self):
        '''Checks if any text or figure is in the margin of pages.'''
            
        pages_image = set()
        pages_text = defaultdict(list)
        perror = []
        for i,p in enumerate(self.pdf.pages):
            if i+1 in self.page_errors: continue
            try: 
                # Parse images.
                for image in p.images:
                    if float(image["top"]) < 56 or float(image["x0"]) < 69 or \
                       595-float(image["x1"]) < (69-self.offset):
                        pages_image.add(i+1)
            
                # Parse texts.
                for j,word in enumerate(p.extract_words()):
                    if float(word["top"]) < 56 or float(word["x0"]) < 69 or \
                       595-float(word["x1"]) < (69-self.offset):
                        pages_text[i+1] += [word["text"], float(word["x0"]), \
                                            595-float(word["x1"])]
            except:
                perror.append(i+1)
                
        if perror:
            self.page_errors.update(perror)
            self.logs["PARSING"]= ["Error occurs when parsing page {}.".format(perror)]
        if pages_image: 
            p = sorted(list(pages_image))
            self.logs["MARGIN"] += ["Images on page {} <may> fall in the margin.".format(p)] 
        if pages_text:
            p = sorted(pages_text.keys())
            self.logs["MARGIN"] += ["Texts on page {} <may> fall in the margin.".format(p)] 
            self.logs["MARGIN"] += ["Details are as follows:", dict(pages_text)] 
        
    
    def page_num(self, paper_type):
        '''Check if the paper exceeds the page limit.'''

        # Set the threshold for different types of paper.
        standards = {"short": 5, "long": 9, "other": float("inf")}
        page_threshold = standards[paper_type.lower()]

        # Find (references, acknowledgements, ethics). 
        markers = [None, None, None]
        if len(self.pdf.pages) <= page_threshold: return
        for i,p in enumerate(self.pdf.pages):
            if i+1 in self.page_errors: continue

            texts = p.extract_text().split('\n')
            for j,line in enumerate(texts):
                if "References" in line and not markers[0]: 
                    # Reference may appear in both paper and appendix.
                    markers[0] = (i+1, j+1)
                candidates = ["Acknowledgements", "Acknowledgments", \
                                "Acknowledgment", "Acknowledgement"]
                if "Acknowl" in line:
                    # Special issue about the spelling of Acknowledgements.
                    if all([x not in line for x in candidates]):
                        self.logs["MISSPELL"] = ["'Acknowledgments' was misspelled."]
                    markers[1] = (i+1, j+1)
                candidates = ["Ethical", "Ethics", "Broader Impact"] 
                if any([x in line for x in candidates]) and not markers[2]:
                    markers[2] = (i+1, j+1)
                    
        markers = list(filter(lambda x: x!=None, markers))
        # All the markers appear after page 9, and none of them starts at line 1 of
        # page 10, there is high probability the paper exceeds the page limit.
        if all((page, line) > (page_threshold + 1, 1) for page, line in markers):
            self.logs["PAGELIMIT"] = ["Paper <may> exceed the page limit because \
            (References, Acknoledgments, Ethics) found on (page,line): {}.".format(markers)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('submission_paths', metavar='file_or_dir', nargs='+',
                        default=[])
    parser.add_argument('--paper_type', choices={"short", "long", "other"},
                        default='long')
    args = parser.parse_args()
    FC = Formatter()
    FC.format_check(**vars(args))
