
import os
import time
import codecs
import urllib
import simplejson
import urllib2
import re

from pprint import pprint

SLEEP_TIME = 20 # seconds

def get_ranked_english():
    '''
    wikitionary has a list of ~40k English words, ranked by frequency of occurance in TV and movie transcripts.
    more details at:
    http://en.wiktionary.org/wiki/Wiktionary:Frequency_lists/TV/2006/explanation

    the list is separated into pages of 1000 or 2000 terms each.
    * the first 10k words are separated into pages of 1000 terms each.
    * the remainder is separated into pages of 2000 terms each:
    '''
    URL_TMPL = 'http://en.wiktionary.org/wiki/Wiktionary:Frequency_lists/TV/2006/%s'
    urls = []
    for i in xrange(10):
        freq_range = "%d-%d" % (i * 1000 + 1, (i+1) * 1000)
        urls.append(URL_TMPL % freq_range)

    for i in xrange(0,15):
        freq_range = "%d-%d" % (10000 + 2 * i * 1000 + 1, 10000 + (2 * i + 2) * 1000)
        urls.append(URL_TMPL % freq_range)

    urls.append(URL_TMPL % '40001-41284')

    ranked_terms = [] # ordered by rank, in decreasing frequency.
    for url in urls:
        html, is_cached = wiki_download(url,'en')
        if not is_cached:
            time.sleep(SLEEP_TIME)
        new_terms = parse_wiki_terms(html)
        ranked_terms.extend(new_terms)

    return ranked_terms

def get_ranked_french():
    '''
    Same for french
    5 pages of 2k rows
    '''
    URL_TMPL = "http://fr.wiktionary.org/wiki/Wiktionnaire:Listes_de_fr%%C3%%A9quence/wortschatz-fr-%s"
    urls = []
    for i in xrange(5):
        freq_range = "%d-%d" % (i * 2000 + 1, (i+1) * 2000)
        urls.append(URL_TMPL % freq_range)

    ranked_terms = [] # ordered by rank, in decreasing frequency.
    for url in urls:
        html, is_cached = wiki_download(url,'fr')
        if not is_cached:
            time.sleep(SLEEP_TIME)
        new_terms = parse_wiki_terms_fr(html)
        ranked_terms.extend(new_terms)

    return ranked_terms

def wiki_download(url,lang):
    '''
    scrape friendly: sleep 20 seconds between each request, cache each result.
    '''
    DOWNLOAD_TMPL = '../data/tv_and_movie_freqlist%s-%s.html'
    freq_range = url[url.rindex('/')+1:]

    tmp_path = DOWNLOAD_TMPL % (freq_range, lang)
    if os.path.exists(tmp_path):
        print 'cached.......', url
        with codecs.open(tmp_path, 'r', 'utf8') as f:
            return f.read(), True
    with codecs.open(tmp_path, 'w', 'utf8') as f:
        print 'downloading...', url
        req = urllib2.Request(url, headers={
                'User-Agent': 'zxcvbn'
                })
        response = urllib2.urlopen(req)
        result = response.read().decode('utf8')
        f.write(result)
        return result, False

def parse_wiki_terms(doc):
    '''who needs an html parser. fragile hax, but checks the result at the end'''
    results = []
    last3 = ['', '', '']
    header = True
    for line in doc.split('\n'):
        last3.pop(0)
        last3.append(line.strip())
        if all(s.startswith('<td>') and not s == '<td></td>' for s in last3):
            if header:
                header = False
                continue
            last3 = [s.replace('<td>', '').replace('</td>', '').strip() for s in last3]
            rank, term, count = last3
            term = term.replace('</a>', '')
            term = term[term.index('>')+1:].lower()
            results.append(term)
    assert len(results) in [1000, 2000, 1284] # early docs have 1k entries, later have 2k, last doc has 1284
    return results


def parse_wiki_terms_fr(doc):
    '''who needs an html parser. fragile hax, but checks the result at the end'''
    results = []
    last    = ''
    header = True
    for line in doc.split('\n'):
        last = line.strip()
        if (last.startswith('<li>')):
            term = re.sub(r'<li>.*<a.*>(.*)</a></li>',r'\1',last)
            results.append(term)
    assert len(results) in [2000] # early docs have 1k entries, later have 2k, last doc has 1284
    return results

def get_ranked_census_names():
    '''
    takes name lists from the the 2000 us census, prepares as a json array in order of frequency (most common names first).

    more info:
    http://www.census.gov/genealogy/www/data/2000surnames/index.html

    files in data are downloaded copies of:
    http://www.census.gov/genealogy/names/dist.all.last
    http://www.census.gov/genealogy/names/dist.male.first
    http://www.census.gov/genealogy/names/dist.female.first
    '''
    FILE_TMPL = '../data/us_census_2000_%s.txt'
    SURNAME_CUTOFF_PERCENTILE = 85 # ie7 can't handle huge lists. cut surname list off at a certain percentile.
    lists = []
    for list_name in ['surnames', 'male_first', 'female_first']:
        path = FILE_TMPL % list_name
        lst = []
        for line in codecs.open(path, 'r', 'utf8'):
            if line.strip():
                if list_name == 'surnames' and float(line.split()[2]) > SURNAME_CUTOFF_PERCENTILE:
                    break
                name = line.split()[0].lower()
                lst.append(name)
        lists.append(lst)
    return lists

def get_ranked_common_passwords():
    lst = []
    for line in codecs.open('../data/common_passwords.txt', 'r', 'utf8'):
        if line.strip():
            lst.append(line.strip())
    return lst

def to_ranked_dict(lst):
    return dict((word, i) for i, word in enumerate(lst))

def filter_short(terms):
    '''
    only keep if brute-force possibilities are greater than this word's rank in the dictionary
    '''
    return [term for i, term in enumerate(terms) if 26**(len(term)) > i]

def filter_dup(lst, lists):
    '''
    filters lst to only include terms that don't have lower rank in another list
    '''
    max_rank = len(lst) + 1
    dct = to_ranked_dict(lst)
    dicts = [to_ranked_dict(l) for l in lists]
    return [word for word in lst if all(dct[word] < dct2.get(word, max_rank) for dct2 in dicts)]

def filter_ascii(lst):
    '''
    removes words with accent chars etc.
    (most accented words in the english lookup exist in the same table unaccented.)
    '''
    return [word for word in lst if all(ord(c) < 128 for c in word)]

def to_js(lst, lst_name):
    return 'var %s = %s;\n\n' % (lst_name, simplejson.dumps(lst))

def main():
    english = get_ranked_english()
    french  = get_ranked_french()
    surnames, male_names, female_names = get_ranked_census_names()
    passwords = get_ranked_common_passwords()

    [english, french,
     surnames, male_names, female_names,
     passwords] = [filter_ascii(filter_short(lst)) for lst in (english, french,
                                                               surnames, male_names, female_names,
                                                               passwords)]

    # make dictionaries disjoint so that d1 & d2 == set() for any two dictionaries
    all_dicts = set(tuple(l) for l in [english, french, surnames, male_names, female_names, passwords])
    passwords    = filter_dup(passwords,    all_dicts - set([tuple(passwords)]))
    male_names   = filter_dup(male_names,   all_dicts - set([tuple(male_names)]))
    female_names = filter_dup(female_names, all_dicts - set([tuple(female_names)]))
    surnames     = filter_dup(surnames,     all_dicts - set([tuple(surnames)]))
    english      = filter_dup(english,      all_dicts - set([tuple(english)]))
    french       = filter_dup(french,       all_dicts - set([tuple(french)]))

    with open('../frequency_lists.js', 'w') as f: # words are all ascii at this point
        lsts = locals()
        for lst_name in 'passwords male_names female_names surnames english french'.split():
            lst = lsts[lst_name]
            f.write(to_js(lst, lst_name))

    print '\nall done! totals:\n'
    print 'passwords....', len(passwords)
    print 'male.........', len(male_names)
    print 'female.......', len(female_names)
    print 'surnames.....', len(surnames)
    print 'english......', len(english)
    print 'french.......', len(french)
    print

if __name__ == '__main__':
    if os.path.basename(os.getcwd()) != 'scripts':
        print 'run this from the scripts directory'
        exit(1)
    main()
