#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import re
from datetime import datetime
from time import time
import xml.etree.ElementTree as ET

"""Where data is inputted"""

__author__ = 'Daniel Campos, Sicong Huang, Hayley Luke, Simola Nayak, Shunjie Wang  '
__email__ = 'dacampos@uw.edu'

AQUAINT2_ROOT = './patas/AQUAINT-2'
DATA_ROOT = './patas/573/Data'

# strings to remove from xml before parsing
CLEAN_RE = re.compile(r'\&.+;')

# what we count as a sentence split (could be replaced with e.g. nltk)
PUNC_SPLIT_RE = re.compile(r'\.')

# examples:
# <doc id = "NYT19980903.0137" />
# /corpora/LDC/LDC02T31/nyt/1998/19980903_NYT
PATH_MAPPING = {
    'AQUAINT': {
        # Do some regex matching to build a path
        # (tag)(year)(month)(day).(doc id)
        'regex': re.compile(r'^([A-Z]{3})([0-9]{4})([0-9]{2})([0-9]{2})\.([0-9]{4})$'),
        'path': '{tag_lower}/{year}/{year}{month}{day}_{tag}',
        'root': './patas/AQUAINT'
    },
    'AQUAINT-2': {
        # Do some regex matching to build a path
        # (tag)(year)(month)(day).(doc id)
        'regex': re.compile(r'^([A-Z]{3})_ENG_([0-9]{4})([0-9]{2})([0-9]{2})\.([0-9]{4})$'),
        'path': '{tag}_eng/{tag}_eng_{year}{month}.xml',
        'root': './patas/AQUAINT-2/data'
    },
}


def build_path(doc_id):
    for corpus, info in PATH_MAPPING.items():
        match = info['regex'].match(doc_id)

        if not match:
            continue

        tag, year, month, day, doc_id = match.groups()
        date = datetime(int(year), int(month), int(day))
        if corpus == 'AQUAINT':
            original_tag = tag
            if tag == 'XIE':
                # No clue why the directory name is different than the file name
                tag = 'XIN'
            if tag != 'NYT':
                # Only the NYT doesn't have this suffix
                tag += '_ENG'
            path = info['path'].format(tag=tag, tag_lower=original_tag.lower(), year=year, month=month, day=day, doc_id=doc_id)
            return os.path.join(info['root'], path), date, corpus
        elif corpus == 'AQUAINT-2':
            path = info['path'].format(tag=tag.lower(), year=year, month=month)
            return os.path.join(info['root'], path), date, corpus

    # If we get here without returning, we didn't figure out the path
    print('Unable to find path for {doc_id}'.format(doc_id=doc_id))
    return None, None, None


class Sentence:
    def __init__(self, text, doc):
        self.document = doc
        self.text = text.strip()

    def __str__(self):
        return self.text

    __repr__ = __str__


class Document:
    def __init__(self, id, date, headline_el, text_el):
        self.id = id
        self.headline = ''
        self.date = date
        if headline_el is not None:
            self.headline = headline_el.text.strip()
        self.text = self.clean_text(text_el)
        self.sentences = [Sentence(s, self) for s in PUNC_SPLIT_RE.split(self.text)]

    def clean_text(self, text_el):
        '''
        Clean all tags out of the body element, leaving just the text
        '''

        text = text_el.text.strip()
        if text == '':
            # Go through P tags
            for p in text_el.findall('P'):
                text += p.text.strip() + ' '

        text = text.replace('\n', '')

        if text == '':
            # still didn't find any text? log it
            print('No text found for document {id}'.format(id=self.id))
        return text


class Topic:
    def __init__(self, id, title):
        self.id = id
        self.title = title

        # List of Document classes
        self.documents = []

    def load_doc(self, doc_id):
        path, date, corpus = build_path(doc_id)

        if not path:
            return

        with open(path, 'r') as f:
            contents = f.read()

        if corpus == 'AQUAINT':
            # Do some basic escaping, and add a root node
            # This is all very hacky, but the xml is extremely poorly formatted...
            # Get rid of amperstands entirely (maybe change in the future?)
            contents = CLEAN_RE.sub('', contents)
            contents = '<root>' + contents + '</root>'
            try:
                group_tree = ET.fromstring(contents)
            except ET.ParseError as e:
                print('Error parsing {path} for {doc_id}'.format(path=path, doc_id=doc_id))
                print(e)
                raise e

            for child in group_tree.findall('DOC'):
                found_doc_id = child.find('DOCNO').text.strip()
                if doc_id == found_doc_id:
                    body = child.find('BODY')
                    headline_el = body.find('HEADLINE')
                    text_el = body.find('TEXT')

                    # Add this document
                    self.documents.append(Document(doc_id, date, headline_el, text_el))
        elif corpus == 'AQUAINT-2':
            contents = CLEAN_RE.sub('', contents)

            try:
                group_tree = ET.fromstring(contents)
            except ET.ParseError as e:
                print('Error parsing {path} for {doc_id}'.format(path=path, doc_id=doc_id))
                print(e)
                raise e

            for child in group_tree.findall('DOC'):
                found_doc_id = child.attrib['id']
                if doc_id == found_doc_id:
                    headline_el = child.find('HEADLINE')
                    text_el = child.find('TEXT')

                    # Add this document
                    self.documents.append(Document(doc_id, date, headline_el, text_el))


def get_topics(path_to_topic):
    '''
    Given a path to a topics xml, returns a list of Topic objects
    '''
    topic_tree = ET.parse(os.path.join(DATA_ROOT, path_to_topic))
    root = topic_tree.getroot()

    topics = []
    for child in root.findall('topic'):
        start_time = time()
        topic_id = child.attrib['id']
        title = child.find('title').text.strip()
        docset_a = child.find('docsetA')

        print('{topic_id} ({title})'.format(topic_id=topic_id, title=title))

        topic = Topic(topic_id, title)

        for doc in docset_a:
            doc_id = doc.attrib['id']
            topic.load_doc(doc_id)

        topics.append(topic)
        print('Topic took {t:.02f} seconds'.format(t=(time() - start_time)))

    return topics


if __name__ == '__main__':
    start_time = time()
    topics = get_topics('Documents/devtest/GuidedSumm10_test_topics.xml')
    print('Full thing took {t:.02f} seconds'.format(t=(time() - start_time)))
    import ipdb; ipdb.set_trace()
