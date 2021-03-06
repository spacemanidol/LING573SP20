#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import gzip
import re
from datetime import datetime
from time import time
import pickle
import xml.etree.ElementTree as ET

"""Where data is inputted"""

__author__ = 'Daniel Campos, Sicong Huang, Hayley Luke, Simola Nayak, Shunjie Wang  '
__email__ = 'dacampos@uw.edu,  huangs33@uw.edu, shunjiew@uw.edu, simnayak@uw.edu, jhluke@uw.edu'

# strings to remove from xml before parsing
CLEAN_RE = re.compile(r'\&.+;|>[0-9]|<[0-9]')

# examples:
# <doc id = "NYT19980903.0137" />
# /corpora/LDC/LDC02T31/nyt/1998/19980903_NYT
PATH_MAPPING = {
    'AQUAINT': {
        # Do some regex matching to build a path
        # (tag)(year)(month)(day).(doc id)
        'regex': re.compile(r'^([A-Z]{3})([0-9]{4})([0-9]{2})([0-9]{2})\.([0-9]{4})$'),
        'path': '{tag_lower}/{year}/{year}{month}{day}_{tag}',
        'root': '/corpora/LDC/LDC02T31' #'/corpora/LDC/LDC02T31/'
    },
    'AQUAINT-2': {
        # Do some regex matching to build a path
        # (tag)(year)(month)(day).(doc id)
        'regex': re.compile(r'^([A-Z]{3})_ENG_([0-9]{4})([0-9]{2})([0-9]{2})\.([0-9]{4})$'),
        'path': '{tag}_eng/{tag}_eng_{year}{month}.xml',
        'root': '/corpora/LDC/LDC08T25/data'#'/corpora/LDC/LDC08T25/data' #'./patas/AQUAINT-2/data' #'Data/LDC08T25/data' #Change this for patas folders aka /corpora/LDC/LDC08T25/data
    },
    'GIGAWORD': {
        # Do some regex matching to build a path
        # (tag)(year)(month)(day).(doc id)
        'regex': re.compile(r'^([A-Z]{3})_ENG_([0-9]{4})([0-9]{2})([0-9]{2})\.([0-9]{4})$'),
        'path': '{tag}_eng/{tag}_eng_{year}{month}.gz',
        'root': '/corpora/LDC/LDC11T07/data'
    },
}


def build_path(base_id):
    for corpus, info in PATH_MAPPING.items():
        match = info['regex'].match(base_id)

        if not match:
            continue

        path = ''
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
            path = os.path.join(info['root'], path)
        elif corpus == 'AQUAINT-2' or corpus == 'GIGAWORD':
            path = info['path'].format(tag=tag.lower(), year=year, month=month)
            path = os.path.join(info['root'], path)

        if os.path.exists(path):
            return path, date, corpus

    # If we get here without returning, we didn't figure out the path
    print('Unable to find path for {doc_id}'.format(doc_id=doc_id))
    return None, None, None

class Sentence:
    def __init__(self, text, doc_headline, doc_date):
        self.text = text.strip()
        self.doc_headline = doc_headline
        self.doc_date = doc_date

    def set_text_parse(self, parse):
        self.text_nlp = parse

    def set_headline_parse(self, headline):
        self.headline_nlp = headline

    def to_dict(self):
        return {
            'text': self.text,
            'doc_headline': self.doc_headline,
            'doc_date': self.doc_date
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            d['text'],
            d['doc_headline'],
            d['doc_date']
        )

    def __str__(self):
        return self.text

    __repr__ = __str__

class Document:
    def __init__(self, nlp, id, date, headline_el, text_el, skip_sentences=False):
        self.id = id
        self.headline = ''
        self.doc_date = date
        self.headline = headline_el
        if headline_el is not None and not isinstance(headline_el, str):
            self.headline = headline_el.text.strip()

        self.text = text_el
        if not isinstance(text_el, str):
            self.text = self.clean_text(text_el)

        if not skip_sentences:
            self.sentences = self.parse_sentences(nlp, self.headline, self.text, self.doc_date)

    def parse_sentences(self, nlp, headline, text, doc_date):
        sentences = []
        nlp_doc = nlp(text)
        for sentence in nlp_doc.sents:
            sentences.append(Sentence(re.sub('\s*\n\s*', ' ', sentence.text), headline, doc_date))
        return sentences

    def get_filtered_sentences(self, min_words):
        '''
        Get filtered sentences from the doc
        * Remove sentences not meeting the minimum word requirement
        * Remove sentences that end in question marks
        * Remove bylines (naively: if first sentence ends in - or _)
        '''

        sentences = []
        first = True
        for sent in self.sentences:
            if len(sent.text.split(' ')) < min_words:
                continue

            if first:
                first = False
                if sent.text[-1] in ('-', '_'):
                    continue

            if sent.text[-1] == '?':
                continue

            sentences.append(sent)

        return sentences


    def clean_text(self, text_el):
        '''
        Clean all tags out of the body element, leaving just the text
        '''

        text = text_el.text.strip()
        if text == '':
            # Go through P tags
            for p in text_el.findall('P'):
                text += p.text.strip() + ' '

        # Clean up repeated spaces and newlines
        text = re.sub(r'\s*\n\s*', ' ', text)

        # Clean up weird quotation marks
        text = re.sub(r"(''|``)", '"', text)

        if text == '':
            # still didn't find any text? log it
            print('No text found for document {id}'.format(id=self.id))
        return text

    def to_dict(self):
        return {
            'id': self.id,
            'headline': self.headline,
            'doc_date': self.doc_date,
            'text': self.text,
            'sentences': [s.to_dict() for s in self.sentences]
        }

    @classmethod
    def from_dict(cls, nlp, d):
        doc = cls(nlp, d['id'], d['doc_date'], d['headline'], d['text'], skip_sentences=True)
        doc.sentences = [Sentence.from_dict(di) for di in d['sentences']]
        return doc

class Topic:
    def __init__(self, nlp, ids, title):
        self.nlp = nlp
        self.id_1, self.id_2 = ids
        self.title = title

        # List of Document classes
        self.documents = []

    @property
    def id(self):
        return self.id_1 + self.id_2

    def load_doc(self, doc_id):
        path, date, corpus = build_path(doc_id)

        if not path:
            return

        if path.endswith('.gz'):
            with gzip.open(path, 'r') as f:
                contents = f.read().decode('utf-8')
        else:
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
                    self.documents.append(Document(self.nlp, doc_id, date, headline_el, text_el))
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
                    self.documents.append(Document(self.nlp, doc_id, date, headline_el, text_el))
        elif corpus == 'GIGAWORD':
            contents = CLEAN_RE.sub('', contents)
            contents = '<root>' + contents + '</root>'
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
                    self.documents.append(Document(self.nlp, doc_id, date, headline_el, text_el))

    def to_dict(self):
        return {
            'id_1': self.id_1,
            'id_2': self.id_2,
            'title': self.title,
            'documents': [d.to_dict() for d in self.documents]
        }

    @classmethod
    def from_dict(cls, nlp, d):
        topic = cls(nlp, (d['id_1'], d['id_2']), d['title'])
        topic.documents = [Document.from_dict(nlp, di) for di in d['documents']]
        return topic


def get_topics(nlp, corpus_dir, corpus_config, use_checkpoint=False):
    '''
    Given a path to a topics xml, returns a list of Topic objects
    '''

    if use_checkpoint:
        try:
            with open(use_checkpoint, 'rb') as f:
                topics = pickle.load(f)
                print('Using data checkpoint')
                return [Topic.from_dict(nlp, d) for d in topics]
        except FileNotFoundError:
            # We'll continue loading normally then
            pass

    topic_tree = ET.parse(os.path.join(corpus_dir, corpus_config))
    root = topic_tree.getroot()

    topics = []
    for child in root.findall('topic'):
        start_time = time()
        topic_id_1 = child.attrib['id'][:-1] #drop a in
        topic_id_2 = child.attrib['id'][-1] # id part 2
        title = child.find('title').text.strip()
        docset_a = child.find('docsetA')

        print('{topic_id} ({title})'.format(topic_id=child.attrib['id'], title=title))

        topic = Topic(nlp, (topic_id_1, topic_id_2), title)

        for doc in docset_a:
            doc_id = doc.attrib['id']
            topic.load_doc(doc_id)

        topics.append(topic)

        print('Topic took {t:.02f} seconds'.format(t=(time() - start_time)))

    if use_checkpoint:
        cleaned_topics = [t.to_dict() for t in topics]
        with open(use_checkpoint, 'wb') as f:
            pickle.dump(cleaned_topics, f)

    return topics
