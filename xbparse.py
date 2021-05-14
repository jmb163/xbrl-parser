#!/Users/Jon/anaconda3/bin/python3
import sys
import glob
from bs4 import BeautifulSoup
import re
import json
from urllib.request import urlopen
import urllib.request
import pandas
import os
import copy
from threading import Thread
import time
from multiprocessing import Process
from datetime import date
import datetime
import random
from reports_getter import Financials
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
usg = re.compile("us-gaap:*")

class DataGrabber():
    '''
    This is good so far but perhaps not complete. I don't know what effect restricted stock has,
    the addition of the user-agent workaround should allow me to pull files when I need and avoid 403
    '''

    #some randomly generated user agents to be used at random when doing HTTP requests.
    u_agents = ["Mozilla/5.0 (Windows; U; Windows NT 6.2) AppleWebKit/532.25.3 (KHTML, like Gecko) Version/5.0.3 Safari/532.25.3",
                "Mozilla/5.0 (Macintosh; U; PPC Mac OS X 10_7_9 rv:3.0; en-US) AppleWebKit/534.32.7 (KHTML, like Gecko) Version/5.0.4 Safari/534.32.7",
                "Opera/9.10 (X11; Linux x86_64; en-US) Presto/2.9.183 Version/10.00",
                "Mozilla/5.0 (iPad; CPU OS 8_2_1 like Mac OS X; en-US) AppleWebKit/532.7.4 (KHTML, like Gecko) Version/3.0.5 Mobile/8B118 Safari/6532.7.4",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 7_0_2 like Mac OS X; sl-SI) AppleWebKit/535.38.4 (KHTML, like Gecko) Version/3.0.5 Mobile/8B114 Safari/6535.38.4",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_5_0 rv:5.0; sl-SI) AppleWebKit/532.48.6 (KHTML, like Gecko) Version/4.0.4 Safari/532.48.6"
                ]
    def u_agent(self):
        return random.choice(self.u_agents)

    def _date_from_string(self, s):
        ymd = s.split(sep='-')
        ymd = [int(x) for x in ymd]
        return datetime.date(ymd[0], ymd[1], ymd[2])

    def __init__(self, ticker, file=False):
        self._issuer_name = ""
        self._cik_number = self._get_cik(ticker)

        # self._insider_filings = self._get_insiders()
        # self._get_insider_holdings()

        #will add some functionality later for updating the database of a company instead of searching for everything
        if file:
            with open("{}_financials.json".format(ticker) ,'r') as f:
                self.reports = json.load(f)
        else:
            self._day = datetime.date.today()
            self._cutoff = datetime.date(self._day.year - 5, self._day.month - 1, self._day.day)  # cutoff date for grabbing reports
            self.reports = self._get_reports()  # collects the indexes of 10-k and 10-Q reports for a quarterly look a financials
            # print(json.dumps(self.reports, indent=2))
            self._fill_reports()

        # print(json.dumps(self._reports, indent=1))

        # with open("{}_holdings.json".format(ticker), 'w') as f:
        #     f.write(json.dumps(self._insider_filings, indent=2))

        if not file:
            with open("{}_financials.json".format(ticker), 'w') as f:
                json.dump(self.reports, f, indent=2)
        # self._print()
        self._sort_reports()

    def _fill_reports(self):
        remove = []
        for report in self.reports:
            print("Fetching data from: {}".format(report['index']))
            rep = Financials(report['index'])
            if not rep.documents:
                remove.append(report)
            else:
                report['data'] = Financials(report['index']).documents
        for bad_report in remove:
            self.reports.remove(bad_report)

    def _pick_after_cutoff(self, index_list, t):
        def date_of(res):
                p = self._date_from_string(res.parent.parent.find("td", {"class":False, 'href':False, 'nowrap':False}).text)
                return p
        good_links = []
        sec_base = "https://www.sec.gov"
        for ref in index_list:
            # print(ref)
            rdate = date_of(ref)
            if(rdate > self._cutoff):
                report = {
                    'index':sec_base + ref['href'],
                    'date':"{}-{}-{}".format(rdate.year, rdate.month, rdate.day),
                    'type':t,
                    'data':None
                }
                good_links.append(report)
        return good_links

    def _sort_reports(self):
        def dfroms(s):
            y, m, d = [int(x) for x in s.split(sep='-')]
            return datetime.date(y, m, d)
        self.reports.sort(key=lambda x: dfroms(x['date']), reverse=True)
        return

    def _get_reports(self):
        '''
        get the links for the 10-Q and 10-K reports all the way back to a given cutoff date
        :return:
        '''
        def dfroms(s):
            y, m, d = [int(x) for x in s.split(sep='-')]
            return datetime.date(y, m, d)

        qbase = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={}&type=10-Q&dateb=&owner=exclude&count=40&search_text=".format(self._cik_number)
        kbase = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={}&type=10-K&dateb=&owner=exclude&count=40&search_text=".format(self._cik_number)
        qreq = urlopen(urllib.request.Request(qbase, headers={"User-Agent": self.u_agent()}))
        qsoup = BeautifulSoup(str(qreq.read(), encoding='utf-8'), 'lxml')

        kreq = urlopen(urllib.request.Request(kbase, headers={"User-Agent": self.u_agent()}))
        ksoup = BeautifulSoup(str(kreq.read(), encoding='utf-8'), 'lxml')

        a_pattern = re.compile(r'/Archives/')
        q_ind = qsoup.find_all("a", {"href":a_pattern})
        k_ind = ksoup.find_all("a", {"href":a_pattern})

        q_links = self._pick_after_cutoff(q_ind, '10-Q')
        k_links = self._pick_after_cutoff(k_ind, '10-K')
        reports = q_links + k_links
        reports.sort(key=lambda x: dfroms(x['date']), reverse=True)
        return reports
        #exclude older files


    def _print(self):
        print("CIK: {}".format(self._cik_number))
        for filing in self._insider_filings:
            print(filing)

    def _get_cik(self, ticker):
        '''
        gets the cik number from the ticker!
        :param ticker:
        :return:
        '''
        searchurl = "http://www.sec.gov/cgi-bin/browse-edgar?" + "action=getcompany&"
        full = searchurl + "CIK={}".format(ticker)
        # with open("website.txt", mode='r') as f:
        #     req = f.read()
        # print(full)
        req = urlopen(urllib.request.Request(full, headers={"User-Agent":self.u_agent()})) #do this to get around 403
        soup = BeautifulSoup(str(req.read(), encoding='utf-8'), 'lxml')
        span = soup.find("span", {"class":"companyName"})
        self._issuer_name = span.text[0:-43]
        cikurl = span.find("a")
        # print(cikurl.text[0:9])
        cik_num = cikurl.text[0:10]
        return cik_num

    def _get_insiders(self):
        '''
        gets a list of CIK numbers and hrefs linked to the large holders of company
        :return:
        '''
        url = "https://www.sec.gov/cgi-bin/own-disp?" + "action=getissuer&" + "CIK={}".format(self._cik_number)
        req = urlopen(urllib.request.Request(url, headers={"User-Agent":self.u_agent()}))
        soup = BeautifulSoup(str(req.read(), encoding='utf-8'), 'lxml')
        rows = soup.find_all("a", {'href':re.compile(r'getowner')})
        issuer_cik = []
        for row in rows:
            i_cik = row['href'][-10:]
            issuer_cik.append({"name":row.text,
                               "url":"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={}&type=&dateb=&owner=only&count=40&search_text=".format(i_cik),
                               "history":[]
                               })
        return issuer_cik

    def _get_insider_holdings(self):
        '''
        Goes through the holders and gets their holding history.

        A little slow, but should only need to be done once.
        :return:
        '''
        for holder in self._insider_filings:
            print("Fetching the history now!")
            holder["history"] = self._get_history(holder['url'])
            print("Got their history!")
            print(json.dumps(holder["history"], indent=2))

    def _get_history(self, url):
        req = urlopen(urllib.request.Request(url, headers={"User-Agent": self.u_agent()}))
        soup = BeautifulSoup(str(req.read(), encoding='utf-8'), 'lxml')
        refs = soup.find_all("a", {'href': re.compile(r'/Archives/')})
        na = "N/A"
        history = []
        # Going to separate more simply
        rows = [row.parent.parent() for row in refs]
        for row in rows:
            f_index = "https://www.sec.gov" + row[2]['href']
            f_type = row[0].text
            if f_type in ['3', '4/A', '5']:
                    continue
            self._parse_filing_xml(f_index, history)
        return history

    def _parse_filing_xml(self, url, history):
        def value(item):
            if not item:
                    return na
            v = item.find("value")
            if(v):
                    return v.text
            else:
                    return na
        def is_common_stock(txt):
            reference = ['common', 'shares', 'stock', 'stocks', 'share']
            check = txt.lower().split(sep=' ')
            similarity = 0
            for word in check:
                    if word in reference:
                            similarity += 1
            if similarity:
                    return True
            else:
                    return False

        na = "N/A"
        req = urlopen(urllib.request.Request(url, headers={"User-Agent": self.u_agent()}))
        soup1 = BeautifulSoup(str(req.read(), encoding='utf-8'), 'lxml')
        ref = soup1.find("a", text=re.compile(r'.xml'))
        xml_doc = "https://www.sec.gov" + ref['href']

        req = urlopen(urllib.request.Request(xml_doc, headers={"User-Agent": self.u_agent()}))
        soup = BeautifulSoup(str(req.read(), encoding='utf-8'), 'lxml')
        if(soup.find("issuername") == None):
            return
        if (soup.find("issuername").text != self._issuer_name):
            return
        #maybe don't use the note for now
        print("---------{}---------".format(xml_doc))
        title = soup.find("securitytitle")
        title = value(title)
        tr_code = soup.find("transactioncode").text
        fdate = soup.find("periodofreport").text
        tdate = soup.find("transactiondate")
        tdate = value(tdate)
        ad = soup.find("transactionacquireddisposedcode")
        ad = value(ad)

        dtable = soup.find("derivativetable")
        ndtable = soup.find("nonderivativetable")

        tshares = na
        tpps = na
        num_shares = soup.find("sharesownedfollowingtransaction")
        if(dtable and ndtable):
            tshares = dtable.find("underlyingsecurityshares")
            tshares = value(tshares)
            tpps = dtable.find("conversionorexerciseprice")
            tpps = value(tpps)
        elif (dtable):
            tshares = dtable.find("underlyingsecurityshares")
            tshares = value(tshares)
            tpps = dtable.find("conversionorexerciseprice")
            tpps = value(tpps)
        elif(ndtable):
            tshares = ndtable.find("transactionshares")
            tshares = value(tshares)
            tpps = ndtable.find("transactionpricepershare")
            tpps = value(tpps)
        else:
            return

        f4 = {
            "transaction_code": tr_code,
            "filing_date": fdate,
            "transaction_date": tdate,
            "title:": title,
            "shares": tshares,
            "price": tpps,
            "A/D": ad,
            "document":xml_doc,
            "current_position":value(num_shares)
            }
        history.append(f4)

    def search(self, statement, record, terms, level=None, exclude=None):
        '''
        :param statement: STRING ['balance_sheet', 'cash_flows', 'income_statement']
        :param terms: LIST words to try matching
        :param level: INT level, enforce more specific or less specific entry (useful for finding entries on tables with structure)
        :param exclude: LIST if words are given in exclude, then a match against one of these will force an entry not to match
        :return:
        '''

        def l_matches(w_list1, w_list2):
            matches = 0
            for word in w_list1:
                if word in w_list2:
                    matches += 1
            return matches
        statements = [
            'balance_sheet',
            'cash_flows',
            'income_statement'
        ]
        if statement not in statements:
            return None
        else:
            base_str = "self.reports[{}]".format(record) + '''['data']''' +"[\'{}\']".format(statement) + '''['table']'''
            search_pool_str = "self.reports[{}]".format(record) + '''['data']''' +"[\'{}\']".format(statement) + '''['flatlist']'''

            base = self.reports[record]['data'][statement]['table']
            search_pool = self.reports[record]['data'][statement]['flatlist']

            hits = {}
            for entry in search_pool:
                matches = l_matches(terms, entry['words'])
                restricted = None
                if exclude:
                    restricted = l_matches(entry['words'], exclude)
                if matches and not restricted:
                    k = int(entry['level'])
                    if k not in hits.keys():
                        hits[k] = []
                    hits[k].append((entry, matches))
            # now write some logic for what to return
            best = {"matches": 0, 'key': None}
            if not level:
                for k in hits.keys():
                    for entry in hits[k]:
                        if entry[1] > best['matches']:
                            best['key'] = entry[0]['key']
                            best['matches'] = entry[1]
            else:
                use = level
                if level not in hits.keys():
                    lv_list = list(hits.keys())
                    lv_list.sort()
                    if level <= 0:
                        use = lv_list[0]
                    elif level > len(lv_list) - 1:
                        use = lv_list[-1]
                    else:
                        use = level
                for entry in hits[use]:
                    if entry[1] > best['matches']:
                        best['key'] = entry[0]['key']
                        best['matches'] = entry[1]
        val = best['key']
        # print(base)
        # print(val)
        eval_string = base_str + val
        ret = eval(eval_string)
        return ret

    def timespan(self, statement, terms, level=None, exclude=None):
        ret = []
        # test = grabber.search(statement, 0, terms, level=level, exclude=exclude)
        # print(terms)
        # print(test)
        for i in range(0, len(self.reports)):
            val = grabber.search(statement, i, terms, level=level, exclude=exclude)
            if not val['value']:
                val = float(0)
            else:
                val = float(val['value'])
                # print("Adding value: {}".format(val))
            ret.append(val)
        return ret[::-1]

    def dates(self):
        def dfroms(s):
            y, m, d = [int(x) for x in s.split(sep='-')]
            return datetime.date(y, m, d)
        stuff = []
        for i in range(0, len(self.reports)):
            val = self.reports[i]['date']
            stuff.append(dfroms(val))
        return stuff[::-1]

def g(x):
        print(json.dumps(x, indent=3))
def dfroms(s):
    y, m, d = s.split(sep='-')
    return datetime.date(int(y), int(m), int(d))
def connect(p1, p2):
    plt.plot([p1[0], p2[0]], [p1[1], p2[1]])

def pr(l):
    for i in l:
        print(i)

def list_operate(f, l1, l2):
    if len(l1) != len(l2):
        return None
    else:
        nl = []
        for i in range(0, len(l1)):
            eval_me = "l1[{}] {} l2[{}]".format(i, f, i)
            nl.append(eval(eval_me))
        return nl

if __name__ == "__main__":
    fname = '20180405mon'
    grabber = DataGrabber("MBII", file=True)  # try to get data for a relatively small company!

    current_assets = grabber.timespan("balance_sheet", ['assets', 'current', 'assets', 'current'])
    current_liabilities = grabber.timespan("balance_sheet", ['liabilities', 'current', 'liabilities', 'current'], exclude=['equity'])

    cash = grabber.timespan("balance_sheet", ['cash', 'equivalents', 'and', 'cash'], exclude=['investments', 'investment', 'restricted'])
    investments = grabber.timespan("balance_sheet", ['short', 'term', 'investments'], exclude=['net', 'total', 'and'])
    receivables = grabber.timespan("balance_sheet", ['accounts', 'receivable', 'net'])
    # print("Investments")
    # pr(investments)
    # print("Cash")
    # pr(cash)
    # print("AL")

    debt = grabber.timespan("balance_sheet", ['current', 'current', 'debt', 'debt'], exclude=['assets', 'liabilities'])
    payables = grabber.timespan("balance_sheet", ['accounts', 'payable', 'net', 'current'], exclude=['receivable'])
    other = grabber.timespan("balance_sheet", ['other', 'current', 'liabilities'])

    bot = list_operate('+', debt, payables)
    bot = list_operate('+', bot, other)

    top = list_operate('+', cash, investments)
    top = list_operate('+', top, receivables)
    quick = list_operate('/', top, other)

    # print("DEBT:")
    # pr(debt)
    # print("PAYABLES:")
    # pr(payables)
    # print("OTHER:")
    # pr(other)
    # pr(receivables)
    # pr(current_assets)
    # pr(current_liabilities)

    # assets = grabber.timespan("balance_sheet", ['assets', 'assets'], exclude=['current'])
    # liabilities = grabber.timespan("balance_sheet", ['liabilities', 'liabilities'], exclude=['current', 'equity', 'assets'])
    # print("Assets")
    # pr(assets)
    # print("Liabilities")
    # pr(liabilities)



    # al = list_operate('-', current_assets, current_liabilities)
    # pr(al)

    dates = grabber.dates()
    # pr(dates)

    # print(json.dumps(grabber.search("balance_sheet",20, ['assets', 'assets'], exclude=['current', 'equity', 'liabilities']), indent=2))
    # print("-----")
    # print(json.dumps(grabber.search("balance_sheet",20, ['liabilities', 'liabilities'], exclude=['current', 'equity', 'assets']), indent=2))

    plt.title("Quick Ratio")
    # plt.scatter([x[0] for x in data], [x[1] for x in data])
    plt.plot(dates, quick, color='red')
    # plt.plot(dates, assets, color='green')
    plt.show()
    pass

# class Financials():
#     '''
#     Try to get the financial information out of a set of xbrl documents
#     1. Examine xsd and find the relevant references for
#         a: Condensed Balance Sheet
#         b: Condensed Statement of Cash Flows
#         c: Condensed Statements Of Operations And Comprehensive Loss
#         d: Condensed Statements Of Changes In Stockholders’ Equity
#     2. Read the presentation linkbase to find the items that make up each statement
#         a. Identify some constants across documents, cash isn't constant in that the
#             gaap item describing cash could be anything. The tables can be broken up
#             according to these items. The reason for doing things this way is to be
#             able to get the statements into a form that is more easily readable, and
#             later, to narrow the choices for gaap items when computing ratios... after all
#             I wouldn't try to find cash in the liabilities, but without having scanned the
#             linkbases, these two things appear in the same context.
#         b. Make the sublists, some items that appear in lists will have more detail in other tables
#             to adjust for this, I will not scan the xsd again, but rather find a calculation arc
#             that describes the summation of these things, this will allow me to create a more
#             detailed statement than what is shown, as I go farther with this program, I will be able
#             to see more data for all statements.
#     3. Read the calculation linkbase, add more detail to the statements
#         a. I could use the calculation linkbase and try to preserve the tree like nature of the data while I'm at
#         perhaps I could create a nested structure, The first layer of items should be totals of something, and so on
#         for each layer.
#         b. It turns out the information in "Changes in Stock Holders Equity" is all derived from the cash flows, either
#         that or the layout only exists in the presentation linkbase
#     4. The reports are working. Now the next step is to add some searching functionality. I can take advantage of the
#         fact that everything is structured, there are some items that seem to show up no matter what in every
#         report, these are usually pretty easy to recognize. For example, if you'd like to find cash, first navigate
#         to the values that part of current assets. This value will sometimes include short term investments, so you
#         to be more specific means to set a preference for items that are children of something.
#         For cash, this would mean you only grab the item under cashandcashequivalents that matches cash, or if you
#         don't care about specificity, or just don't care about whether short term investments are included in cash
#         you could set your preference for a more general item
#     5. Still a couple things to work out, for instance, some reports contain negative numbers directly in the xbrl,
#         while negative numbers are indicated in other documents by the decimals attribute, I should just check at load
#         time whether or not the gaap fact in question has the attribute decimals
#
#         check whether or not all the share based information shows up in the parenthetical, it usually does, but the code
#         seems to break in the somewhat likely case that I didn't pull it from somewhere else
#     '''
#     def _check_folder(self, folder):
#         self._directory = os.getcwd() + '/' + folder
#         #instance will be checked by not matching these
#         files = os.listdir(self._directory)
#         files_len = len(files)
#         if files_len != 6:
#             raise Exception("Wrong number of files")
#         sufs = self._suffixes
#         for file in files:
#             failed = True
#             for suf in sufs:
#                 if re.search(suf, file):
#                     failed = False
#                     break
#             if failed:
#                 raise Exception("Bad files!")
#         self._ticker = files[0].split(sep='-')[0]
#         return
#
#     def _load_file(self, file):
#         return BeautifulSoup(open(file, 'r'), 'lxml').find_all()
#
#     def _clean_definition(self, definition):
#         '''
#         For cleaning up definitions with weird escape characters, sometimes
#         these are html entities
#         :param definition:
#         :return:
#         '''
#         clean = html.unescape(definition)
#         new_str = ''
#         for letter in clean:
#             if not letter.isalnum():
#                 if letter == ' ':
#                     new_str+=letter
#                 else:
#                     continue
#             else:
#                 new_str += letter
#         return new_str.lower()
#
#     def _load_xml(self):
#         directory = self._directory
#         files = os.listdir(directory)
#         files = [directory+'/'+x for x in files]
#         #files are validated (kind of, I didn't bother checking the dei or anything) try to load them now
#         #assign each file to a suffix
#         for file in files:
#             for suf in self._suf_dic.keys():
#                 if re.search(self._suf_dic[suf], file):
#                     self._suf_dic[suf] = file
#         self._calculation_base = self._load_file(self._suf_dic['cal'])
#         self._presentation_base = self._load_file(self._suf_dic['pre'])
#         self._label_base = self._load_file(self._suf_dic['lab'])
#         self._definition_base = self._load_file(self._suf_dic['def'])
#         self._schema = self._load_file(self._suf_dic['schema'])
#         self._instance = self._load_file(self._suf_dic['instance'])
#
#     def _pmatch(self, definition, keywords_list):
#         if 'statement' not in definition.lower():
#             return 0
#         else:
#             check_def = self._clean_definition(definition)
#             check_def = check_def.split(sep=' ')
#             num_matches = 0
#             for word in check_def:
#                 for key in keywords_list:
#                     if word == key:
#                         num_matches += 1
#             return num_matches
#
#     def _matches(self, definition, keywords_list):
#         '''
#         :param definition:
#         :param keywords_list:
#         :return:
#         '''
#         #statement check
#         if 'statement' not in definition.lower():
#             return 0
#         elif '(parenthetical)' in definition.lower():
#             return 0
#         else:
#             check_def = self._clean_definition(definition)
#             check_def = check_def.split(sep=' ')
#             num_matches = 0
#             for word in check_def:
#                 for key in keywords_list:
#                     if word == key:
#                         num_matches += 1
#             return num_matches
#
#     def _statements(self):
#         '''
#         This is heuristic, not exact, it would be more painful to and time consuming
#         to check the industry and sector reference for what kind of reports they
#         have, and would probably just create problems
#
#         I can't believe this worked :)
#         :return:
#         '''
#         self._balance_sheet_ref = None
#         self._cash_flow_ref = None
#         self._equity_change_ref = None
#         self._income_ref = None
#         self._parenthetical_ref = None
#         statement_refs = {
#             'balancesheet': ['balance', 'sheet', 'sheets', 'financial', 'position'],
#             'cashflows': ['cash', 'flow', 'flows'],
#             'operations': ['income', 'statement', 'operations', 'loss'],
#             'equitychange': ['changes','change', 'in', 'stockholders', 'equity'],
#             'parenthetical':['balance', 'sheet', '(parenthetical)', 'parenthetical', 'condensed']
#         }
#         roles = self._schema[0].find_all('link:roletype')
#         for key in statement_refs.keys():
#             best = {'num_matches':0,'item':None}
#             for role in roles:
#                 definition = str(role.find(name='link:definition').text).lower()
#                 matches = self._matches(definition, statement_refs[key])
#                 if key == 'parenthetical':
#                     matches = self._pmatch(definition, statement_refs[key])
#                 if matches > best['num_matches']:
#                     best['num_matches'] = matches
#                     best['item'] = role.attrs['roleuri']
#             if key == 'balancesheet':
#                 self._balance_sheet_ref = best['item']
#             elif key == 'cashflows':
#                 self._cash_flow_ref = best['item']
#             elif key == 'operations':
#                 self._income_ref = best['item']
#             elif key == 'equitychange':
#                 self._equity_change_ref = best['item']
#             elif key == 'parenthetical':
#                 self._parenthetical_ref = best['item']
#         # print(self._balance_sheet_ref)
#         # print(self._cash_flow_ref)
#         # print(self._equity_change_ref)
#         # print(self._income_ref)
#         # print(self._parenthetical_ref)
#         return
#
#     def _statement_format(self, flat_list, statement):
#         '''
#         takes a flat list from a parsed arc, and creates a format, this format will be copied depending on the date
#         periods, etc.
#         :param flat_list:
#         :return:
#         '''
#         def new_item():
#             return {'items':{}, 'value':None}
#         self._formats[statement] = {}
#         base = 'self._formats[\'{}\']'.format(statement) #base address
#         for item in flat_list:
#             exec('{}{} = new_item()'.format(base, item[2]))
#         self._formats[statement]['flatlist'] = flat_list
#         return
#
#     def _print_format(self, statement):
#         print(json.dumps(self._formats[statement], indent=4))
#
#     def _items_from_address(self, address):
#         bad_punc = re.compile(r'[^A-Za-z0-9\-\:]+')
#         new_str = address
#         new_str = re.sub(bad_punc, ' ', new_str)
#         new_str = new_str.strip()
#         items = new_str.split()
#         bad_ind = []
#         for i in range(len(items)):
#             if items[i] == 'items':
#                 bad_ind.append(i)
#         new_items = []
#         for i in range(len(items)):
#             if i not in bad_ind:
#                 new_items.append(items[i])
#         return new_items
#
#     def _new_address(self, item_list):
#         def brackets(s):
#             return '[\'' + s + '\']'
#         new_address = ''
#         for i in range(0, len(item_list)-1):
#             new_address += brackets(item_list[i])
#             new_address += '[\'items\']'
#         new_address += brackets(item_list[-1])
#         return new_address
#
#
#
#     def _parse_arc(self, tags, statement):
#         '''
#         takes some bs4 tags and returns a nested JSON object
#
#         Right now I can cut the data into subsections for its respective tables, but the way it's computed isn't
#         exactly the way that you'd want it to be.
#
#         liabilitiesandstockholdersequity is actually the parent of liabilities in the calculation arc, this could
#         be broken for this document, I'm not sure though, so instead I'll define some meta values that seem to
#         persist across different taxonomies and go from there
#
#         Now I just have to make the data go where it's supposed to, no company seems to the things too differently
#
#         some companies think it's bad to report total liabilities, I however really like to read the total liabilities
#         so some fixes are in order, Liabilities will always fall under liabilities and stockholdersequity within the
#         calculation arc, but sometimes the liabilities won't be put under the group name us-gaap:Liabilities
#
#         To fix this, every item in liabilities and stockholders equity that isn't explicitly marked as something
#         from stockholders equity will be subordinated to Liabilities (including every item of LiabilitiesCurrent if
#         necessary
#         :param tags:
#         :return:
#         '''
#         print("Parsing the arc\n")
#         def get_item_name(linktofrom):
#             name = linktofrom
#             name = name.split(sep='_')
#             if 'us-gaap' in name:
#                 ind = name.index('us-gaap')
#             else:
#                 ind = name.index(self._ticker)
#             name = name[ind+1]
#             name = 'us-gaap:' + name
#             return name
#         def xto(tag):
#             return tag.attrs['xlink:to']
#         def xfrom(tag):
#             return tag.attrs['xlink:from']
#         def eval_address(base, address):
#             return eval('{}{}'.format(base, address))
#         def brackets(s):
#             return '[\'' + s + '\']'
#         # calc_tags = tags[0].find_all('calculationarc')
#         # print(tags)
#
#         calc_tags = []
#         calc_pattern = re.compile(r'calculationarc')
#         for result in tags:
#                 subset = result.find_all(calc_pattern)
#                 calc_tags += subset
#         # print(calc_tags)
#         stuff = []
#         for i in range(0, len(calc_tags)):
#             fro = get_item_name(xfrom(calc_tags[i]))
#             t = get_item_name(xto(calc_tags[i]))
#             stuff.append(fro)
#             stuff.append(t)
#             # print('from: {}'.format(fro))
#             # print('to: {}'.format(t))
#         items = list(dict.fromkeys(stuff))
#         # print(items)
#         new = {}
#         for item in items:
#             new[item] = {'to':[], 'from':[]}
#         # for item in items:
#         #     print(item)
#         for item in items:
#             for i in range(0, len(calc_tags)):
#                 fro = get_item_name(xfrom(calc_tags[i]))
#                 t = get_item_name(xto(calc_tags[i]))
#                 if item == fro:
#                     new[item]['to'].append(t)
#                 elif item == t:
#                     new[item]['from'].append(fro)
#             new[item]['from'] = list(dict.fromkeys(new[item]['from']))
#             new[item]['to'] = list(dict.fromkeys(new[item]['to']))
#         if 'us-gaap:Liabilities' not in items and statement == 'balancesheet':
#             #do something here
#             '''
#             I thought about doing something with the root addresses, however it would really be easier to
#             just insert 'us-gaap:Liabilities' into the 'to' of LiabilitiesandStockholdersEquity
#
#             'us-gaap:Liabilities'[to] should be ['us-gaap:LiabilitiesAndStockholdersEquity']
#             '''
#
#             print("Missing the total Liabilities")
#             self._missing_liabilities = True
#             print(json.dumps(new, indent=2))
#             subs = copy.deepcopy(new["us-gaap:LiabilitiesAndStockholdersEquity"]['to'])
#             new['us-gaap:Liabilities'] = {}
#             new['us-gaap:Liabilities']['from'] = ["us-gaap:LiabilitiesAndStockholdersEquity"]
#             new['us-gaap:Liabilities']['to'] = []
#             valid = []
#             wrong_stuff = re.compile('^us-gaap:StockholdersEquity')
#             for item in subs:
#                 if not re.match(wrong_stuff, item):
#                     valid.append(item)
#             new["us-gaap:LiabilitiesAndStockholdersEquity"]['to'].append('us-gaap:Liabilities')
#             new["us-gaap:LiabilitiesAndStockholdersEquity"]['to'] = [x for x in new["us-gaap:LiabilitiesAndStockholdersEquity"]['to'] if x not in valid]
#             new['us-gaap:Liabilities']['to'] = valid
#             #subs are the children of that category
#             # print(json.dumps(new, indent=3))
#         key_copy = list(new.keys()).copy()
#         level = 0
#         level_items = {}
#         flat_list = []
#         while len(key_copy) > 0:
#             level_items[str(level)] = []
#             if level == 0:
#                 used = []
#                 for key in key_copy:
#                     if len(new[key]['from']) == 0:
#                         i_tup = (key, new[key], brackets(key))
#                         flat_list.append(i_tup)
#                         level_items[str(level)].append(i_tup)
#                         used.append(key)
#                 for item in used:
#                     key_copy.remove(item)
#                 level += 1
#             else:
#                 parents = level_items[str(level - 1)] #list of tuples
#                 child_lists = []
#                 used = []
#                 for parent in parents:
#                     child_lists.append(parent[1]['to'])
#                 for i in range(0, len(child_lists)):
#                     child_list = child_lists[i]
#                     parent_address = parents[i][2]
#                     for child in child_list:
#                         child_address = parent_address + '''['items']''' + brackets(child)
#                         c_tup = (child, new[child], child_address)
#                         level_items[str(level)].append(c_tup)
#                         flat_list.append(c_tup)
#                         used.append(child)
#                 for item in used:
#                     key_copy.remove(item)
#                 level += 1
#             #now the breakdown is working, however, I have to be able to insert actual values there
#         # for item in level_items.keys():
#         #     stuff = level_items[item]
#         #     for thing in stuff:
#         #         print(thing[2])
#         #keep the flat_list, it will tell me how to format the data in the given statement
#         #I should make copies of the format without the data, because there will be different date contexts
#         #to fill in the data for. I should probably just return or set the format from here, a different function
#         #should handle the date contexts and the actual loading from the instance document
#         self._statement_format(flat_list, statement)
#         return
#
#     def _new_element(self):
#         return {'items':[], 'value':0}
#
#     def _parse_shares(self, shares_link):
#         '''
#         For parsing share based information. Makes it possible to track shares issued/outstanding across time
#         :param shares_link:
#         :return:
#         '''
#         def brackets(s):
#             return '[\'' + s + '\']'
#         locs = shares_link[0].find_all('link:loc')
#         # print(len(locs))
#         values = []
#         for loc in locs:
#             gaap_item = loc.attrs['xlink:href'].split(sep='#')[-1]
#             if 'abstract' in gaap_item.lower():
#                 continue
#             else:
#                 gaap_item = 'us-gaap:' + gaap_item.split(sep='_')[-1]
#                 p_tup = (gaap_item, None, brackets(gaap_item))
#                 values.append(p_tup)
#         self._statement_format(values, 'parenthetical')
#         for key in self._formats['parenthetical'].keys():
#             if key != 'flatlist':
#                 del self._formats['parenthetical'][key]['items']
#         return
#
#     def _get_proper_link(self, base, linktype, role):
#         link = None
#         try:
#             link = base[0].find(linktype, {'xlink:role': role})
#         except:
#             print(base)
#         if not link:
#             link = base.find(linktype, {'xlink:role':role})
#             return link
#         else:
#             return link
#
#     def _read_statement(self):
#         '''
#         top level items will have an items category, and a total value,
#         :return:
#         '''
#
#         # print('Refs are: ')
#         # print(self._balance_sheet_ref)
#         # print(self._cash_flow_ref)
#         # print(self._income_ref)
#         # print(self._parenthetical_ref)
#
#         # for i in range(0, len(self._calculation_base)):
#         #     print(i)
#         #     print(self._calculation_base[i])
#
#         balance_link = self._calculation_base[0].find_all(attrs={'xlink:role':self._balance_sheet_ref})
#         cashflow_link = self._calculation_base[0].find_all(attrs={'xlink:role':self._cash_flow_ref})
#         operation_link = self._calculation_base[0].find_all(attrs={'xlink:role':self._income_ref})
#         shares_link = self._presentation_base[0].find_all(attrs={'xlink:role':self._parenthetical_ref})
#         # balance_link = self._get_proper_link(self._calculation_base, 'link:calculationlink', self._balance_sheet_ref)
#         # cashflow_link = self._get_proper_link(self._calculation_base, 'link:calculationlink', self._cash_flow_ref)
#         # operation_link = self._get_proper_link(self._calculation_base, 'link:calculationlink', self._income_ref)
#         # shares_link = self._get_proper_link(self._presentation_base, 'link:presentationlink', self._parenthetical_ref)
#
#         # print("Bases are:" )
#         # print(balance_link)
#         # print(cashflow_link)
#         # print(operation_link)
#         # print(self._parenthetical_ref)
#         # print(shares_link)
#
#         self.report = {}
#         self._parse_arc(balance_link, 'balancesheet')
#         self._parse_arc(cashflow_link, 'cashflows')
#         self._parse_arc(operation_link, 'operations')
#         self._parse_shares(shares_link)
#         # print("Balance Sheet")
#         # self._print_format('balancesheet')
#         # print("Cash Flows")
#         # self._print_format('cashflows')
#         # print("Operations")
#         # self._print_format('operations')
#         # print("Shares")
#         # self._print_format('parenthetical')
#         return
#
#         #I will not be using the equity link, it's a little bit too hard to parse, and it's values are all
#         #derived from the other statements
#     def _get_facts(self):
#         '''
#         this will get all the gaap facts
#         another function will populate the formatted statements
#         :return:
#         '''
#         tags = self._instance[0]
#         gaap_items = []
#         facts = tags.find_all(re.compile('^us-gaap:*'))
#         temp_list = []
#         for fact in facts:
#             if 'contextref' in list(fact.attrs.keys()) and not len(fact.text) > 50:
#                 temp_list.append(fact)
#         for fact in temp_list:
#             gaap_items.append({fact.name:{'text':fact.text, 'context':fact.attrs['contextref']}})
#         self._gaap_items = gaap_items
#         return
#
#     def _set_contexts(self):
#         '''
#         This function should handle all of the logic for getting stuff to go into the statements
#
#         First I'll have to figure out what contexts to keep, and which to throw away. Some of the contexts are
#         just subsets of another, so in essence I just have to figure out which contexts for a given set of
#         items are the
#         :return:
#         '''
#         def matching_items(key_list):
#             '''
#             return a subset of gaap items where each member of the set has a key that is in
#             key list
#
#             Now make a list of the contexts, find the one that occurs most, and anything that also occurs
#             about that much is probably a relevant context to pull items from for the given statement
#
#             This could only really break in the most extreme circumstances, for the MSFT documents I use
#             as an example, the context occurrences are equal, however for ZSAN, the two contexts of the
#             balance sheet have unequal occurrences in gaap items
#
#             I could probably avoid breaking anything if I just check whether or one context is a substring
#             of another
#             :param key_list:
#             :return:
#             '''
#             ret = []
#             for key in key_list:
#                 for gitem in self._gaap_items:
#                     gkey = list(gitem.keys())[0]
#                     # print('key:{} , gkey:{}'.format(key, gkey))
#                     if key.lower() == gkey.lower():
#                         if gitem in ret:
#                             continue
#                         ret.append(gitem)
#             return ret
#
#         def ret_key(dic_list):
#             return list(dic_list.keys())[0]
#
#         statements = self._formats.keys()
#         self._contexts = {}
#         for statement in statements:
#             items = self._formats[statement]['flatlist']
#             item_len = len(items)
#             # for i in items:
#             #     print(i[0])
#             # print("There are {} items".format(item_len))
#             contexts = {}
#             klist = [x[0] for x in items]
#             sub_items = matching_items(klist)
#             # print('Sub items')
#             # for s in sub_items:
#             #     print(s)
#             for item in sub_items:
#                 k = ret_key(item)
#                 if item[k]['context'] in contexts.keys():
#                     contexts[item[k]['context']] += 1
#                 else:
#                     contexts[item[k]['context']] = 1
#             remove = []
#             for con in contexts.keys():
#                 if self._context_tolerance == None:
#                     toler = 10
#                 else:
#                     toler = self._context_tolerance
#                 if not contexts[con] >= (item_len-toler) or contexts[con] <= 3:
#                     remove.append(con)
#             for rem in remove:
#                 contexts.pop(rem)
#             self._contexts[statement] = list(contexts.keys())
#             if statement == 'parenthetical':
#                 self._contexts[statement] = self._contexts['balancesheet']
#                 self._context_tolerance = len(list(self._formats['parenthetical']['flatlist']))//2
#                 #the context tolerance is here because in some reports the context occurrences will
#                 #match the gaap items for a statement, but sometimes it will not
#         return
#
#     def compare_date(self, d1, d2):
#         '''
#         d1 - d2 = days since d2 to d1
#         :param d1:
#         :param d2:
#         :return:
#         '''
#         d1_l = d1.split(sep='-')
#         d2_l = d2.split(sep='-')
#         d1_l = [int(x) for x in d1_l]
#         d2_l = [int(x) for x in d2_l]
#         y1, m1, day1 = d1_l
#         y2, m2, day2 = d2_l
#         date1 = date(y1, m1, day1)
#         date2 = date(y2, m2, day2)
#         delta = date1 - date2
#         return delta.days
#
#
#     def _parse_contexts(self):
#         '''
#         Get the start date, end date, or instant of a context, will be used later on for the statements
#
#         The current way doesn't seem to work, find the latest start and end dates for each statement
#         The Documente Date will be more easily found in the schema, look there first, find the latest date.
#         :return:
#         '''
#         statements = list(self._formats.keys())
#
#         #self._report_date = self._instance[0].find('dei:documentperiodenddate').text
#
#
#         print(statements)
#         for statement in statements:
#             self._contexts[statement] = dict.fromkeys(self._contexts[statement])
#             for key in self._contexts[statement].keys():
#                 self._contexts[statement][key] = {}
#             ctexts = self._contexts[statement]
#             for text in ctexts:
#                 ctag = self._instance[0].find('xbrli:context', {'id':text})
#                 if not ctag:
#                     ctag = self._instance[0].find('context', {'id':text})
#                 self._contexts[statement][text]['instant'] = None
#                 self._contexts[statement][text]['startdate'] = None
#                 self._contexts[statement][text]['enddate'] = None
#                 instant_pattern = re.compile('instant')
#                 start_pattern = re.compile('startdate')
#                 end_pattern = re.compile('enddate')
#                 if not ctag:
#                     continue
#                 if ctag.find(instant_pattern):
#                     self._contexts[statement][text]['instant'] = ctag.find(instant_pattern).text
#                     self._contexts[statement][text]['startdate'] = None
#                     self._contexts[statement][text]['enddate'] = None
#                 elif ctag.find(start_pattern):
#                     self._contexts[statement][text]['instant'] = None
#                     self._contexts[statement][text]['startdate'] = ctag.find(start_pattern).text
#                     self._contexts[statement][text]['enddate'] = ctag.find(end_pattern).text
#         return
#
#     def _pretty_number(self, num):
#         '''
#         takes a number as string, adds some commas to it so it's more readable
#         :param num:
#         :return:
#         '''
#         if num==None:
#             return num
#         elif float(num) < 1 and float(num) >= 0:
#             return num
#         if len(num) <= 3:
#             return num
#         integer = int(num)
#         if integer < 0:
#             ret = '-' + '{:,}'.format(abs(integer))
#             return ret
#         else:
#             return '{:,}'.format(integer)
#
#     def _copy_thread(self, dest, src):
#         cop = copy.deepcopy(src)
#         dest.update(cop)
#         return
#
#     def _fill_statements(self):
#         '''parsing the instance like this could be what's so slow, I should gather all the gaap facts and
#         then parse the tags from that instead of the entire instance
#         '''
#         gaap_items = self._instance[0].find(re.compile('^us-gaap:'))
#         ad_split = re.compile('\'[a-zA-Z\:\-]+\'')
#
#         def get_item_fast(instance, name, context):
#             ret = gaap_items.find(name.lower(), {'contextref':context})
#             if not ret:
#                 return get_item_slow(instance, name, context)
#             else:
#                 if 'decimals' in ret.attrs:
#                     if float(ret.text) < 0 and '-' not in ret.text:
#                         return '-' + ret.text
#                 return ret.text
#
#         def get_item_slow(instance, name, context):
#             ret = instance[0].find(name.lower(), {'contextref':context})
#             if not ret:
#                 return None
#             if 'decimals' in ret.attrs:
#                 if float(ret.text) < 0 and '-' not in ret.text:
#                     return '-' + ret.text
#             return ret.text
#
#         def load_value(base, address, value):
#             estr = '{}{}[\'value\'] = \'{}\''.format(base, address, value)
#             return estr
#
#         def reference_load(base, address, value):
#             address_items = re.findall(ad_split, address)
#             for i in range(len(address_items)):
#                 address_items[i] = address_items[i].replace("'", "")
#             temp = base
#             for item in address_items:
#                 temp = temp[item]
#             temp = value
#
#
#         statements = list(self._formats.keys())
#         self.reports = {}
#         #self._json_doc = {}
#         copy_thread_count = 0
#         copy_jobs = []
#
#         for statement in statements:
#             contexts = self._contexts[statement].keys()
#             self.reports[statement] = {}
#             #self._json_doc[statement] = {}
#             # src_string = json.dumps(self._formats[statement])
#             for context in contexts:
#                 self.reports[statement][context] = {}
#                 self.reports[statement][context].update(copy.deepcopy(self._formats[statement]))
#                 #self._json_doc[statement][context] = {}
#                 source = self._formats[statement]
#                 report_dest = self.reports[statement][context]
#                 #json_dest = self._json_doc[statement][context]
#                 #format for thread worker is destination, source
#                 c_job_report = [report_dest, source]
#                 #c_job_json = [json_dest, source]
#                 copy_jobs.append(c_job_report)
#                 #copy_jobs.append(c_job_json)
#                 copy_thread_count += 1
#                 # self.reports[statement][context] = copy.deepcopy(self._formats[statement])
#                 # self._json_doc[statement][context] = copy.deepcopy(self._formats[statement])
#         threads = []
#         # start = time.time()
#         # for i in range(0, copy_thread_count):
#         #     new_job = Thread(target=self._copy_thread, args=[copy_jobs[i][0], copy_jobs[i][1]])
#         #     threads.append(new_job)
#         #     threads[-1].start()
#         # for i in range(0, copy_thread_count):
#         #     threads[i].join()
#         # end = time.time()
#         # print("Threads took {}s".format(round(end-start, 2)))
#
#         start = time.time()
#         for statement in statements:
#             contexts = self._contexts[statement].keys()
#             # self.reports[statement] = {}
#             # self._json_doc[statement] = {}
#             for context in contexts:
#                 # self.reports[statement][context] = copy.deepcopy(self._formats[statement])
#                 # self._json_doc[statement][context] = copy.deepcopy(self._formats[statement])
#                 del self.reports[statement][context]['flatlist']
#
#                 #del self._json_doc[statement][context]['flatlist']
#                 names = self._formats[statement]['flatlist']
#                 for name in names:
#                     item_name = name[0]
#                     address = name[2]
#                     value = get_item_fast(self._instance, item_name, context)
#                     if value:
#                         value.strip(' ')
#                     base = 'self.reports[\'{}\'][\'{}\']'.format(statement, context)
#                     jsbase = 'self._json_doc[\'{}\'][\'{}\']'.format(statement, context)
#                     if value == None or value == '':
#                         #exec(load_value(jsbase, address, '0'))
#                         exec(load_value(base, address, float(0)))
#                         # reference_load(self.reports[statement][context], address, '0.0')
#                         continue
#                     #exec(load_value(jsbase, address, self._pretty_number(value)))
#                     exec(load_value(base, address, float(value)))
#                     # reference_load(self.reports[statement][context], address, value)
#
#         end = time.time()
#         print("Threads took {}s".format(round(end-start, 2)))
#         return
#
#     def _set_default_contexts(self):
#         '''
#         sets the default context depending on the report date
#         choose the most recent
#         :return:
#         '''
#         self._defaults = {
#             'balancesheet':None,
#             'cashflows':None,
#             'parenthetical':None,
#             'operations':None
#         }
#         statements = list(self._formats.keys())
#
#
#
#         for statement in statements:
#             contexts = list(self._contexts[statement].keys())
#             #now determine which context is the most recent
#             print(contexts)
#             best = contexts[0]
#             for context in contexts:
#                 instant = self._contexts[statement][context]['instant']
#                 start = self._contexts[statement][context]['startdate']
#                 end = self._contexts[statement][context]['enddate']
#                 if instant:
#                     if self.compare_date(instant, self._contexts[statement][best]['instant']) >= 0:
#                         best = context
#                         self._defaults[statement] = self._contexts[statement][context]
#                         self._defaults[statement]['ref'] = context
#                 else:
#                     delta = self.compare_date(end, start)
#                     if delta > 100 and statement != 'cashflows':
#                         continue
#                     else:
#                         if end == self._report_date:
#                             best = context
#                             self._defaults[statement] = self._contexts[statement][context]
#                             self._defaults[statement]['ref'] = context
#         return
#
#
#
#     def __str__(self):
#         if not self._str_representation:
#             self._str_representation = json.dumps(self.reports, indent=3)
#         return self._str_representation
#
#     def _set_roots(self):
#         '''
#         Tries to figure out what's what for the roots in the operations table. Some things appear across all the statements
#         while others are just a different way of saying the same thing. Hopefully any given company isn't so different
#         that I can't figure out the roots of the values that I really want
#         :return:
#         '''
#
#
#     def __init__(self, folder):
#         '''
#         folder is a relative path to a folder containing the xbrl instance, schema, and linkbases.
#
#         Later on I can add some functionality to grab data from edgar, but for now I will just use local files
#         :param folder:
#         '''
#         start = time.time()
#         self._suf_dic = {
#             'cal': re.compile('_cal\.xml'),
#             'def': re.compile('_def\.xml'),
#             'lab': re.compile('_lab\.xml'),
#             'pre': re.compile('_pre\.xml'),
#             'schema': re.compile('\.xsd'),
#             'instance': re.compile('\.xml')
#         }
#         self._context_tolerance = None
#         self._str_representation = None
#         self._ticker = None
#         self._report_date = None
#         self._missing_liabilities = False
#         self._formats = {} #empty statements with the correct structure
#         self._suffixes = self._suf_dic.values()
#         self._folder = folder
#         self._check_folder(folder)
#         self._load_xml()
#         self._statements()
#         self._read_statement()
#         self._get_facts()
#         self._set_contexts()
#         self._parse_contexts()
#
#         #now the contexts should have dates attached to them
#         #this next part should be more simple
#
#         self._fill_statements()
#         #fill statement is taking up all of the computing time
#
#         # print("Took {} seconds to load report".format(end - start))
#         self._set_default_contexts()
#         #these roots will help people choose items
#         self.roots = {
#             'balancesheet': {
#                 'assets': self._address_of('balancesheet', 'us-gaap:Assets'),
#                 'currentassets': self._address_of('balancesheet', 'us-gaap:AssetsCurrent'),
#                 'liabilities': self._address_of('balancesheet', 'us-gaap:Liabilities'),
#                 'currentliabilities': self._address_of('balancesheet', 'us-gaap:LiabilitiesCurrent'),
#                 'stockholdersequity': self._address_of('balancesheet', 'us-gaap:StockholdersEquity'),
#                 'cash': self._address_of('balancesheet', 'us-gaap:CashCashEquivalentsAndShortTermInvestments')
#             },
#             'cashflows': {
#                 'operating':self._address_of('cashflows', 'us-gaap:NetCashProvidedByUsedInOperatingActivities'),
#                 'financing':self._address_of('cashflows', 'us-gaap:NetCashProvidedByUsedInFinancingActivities'),
#                 'investing':self._address_of('cashflows', 'us-gaap:NetCashProvidedByUsedInInvestingActivities'),
#                 'cashflow': self._address_of('cashflows', 'us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect')
#             },
#             'operations': {
#                 'gross':self._address_of('operations', ['us-gaap:GrossProfit', 'us-gaap:OperatingIncomeLoss']),
#                 'net':self._address_of('operations', 'us-gaap:NetIncomeLoss')
#             },
#             'parenthetical': {
#                 'sharesoutstanding':self._address_of('parenthetical', "us-gaap:CommonStockSharesOutstanding"),
#                 'sharesauthorized':self._address_of('parenthetical', "us-gaap:CommonStockSharesAuthorized"),
#                 'sharesissued':self._address_of('parenthetical', "us-gaap:CommonStockSharesIssued")
#             }
#         }
#         if self._missing_liabilities:
#             self._fix_liability()
#         # print(json.dumps(self.roots, indent=3))
#         # for item in self._formats['operations']['flatlist']:
#         #     print(json.dumps(item[2], indent=3))
#         # for statement in self._formats.keys():
#         #     print(statement)
#         #     for item in self._formats[statement]['flatlist']:
#         #         print(json.dumps(item[2], indent=3))
#         # print(json.dumps(self._formats, indent=3))
#
#     def _num_matches(self, gaapitem, search):
#         if gaapitem == None:
#             return None
#         swords = []
#         gwords = []
#         if type(search) == type(''):
#             swords = self._word_split(search)
#         else:
#             pass
#         if type(gaapitem) == type(''):
#             gwords = self._word_split(gaapitem)
#         else:
#             pass
#         # [print(x) for x in gwords]
#         # [print(x) for x in swords]
#
#         num = 0
#         for s in swords:
#             for g in gwords:
#                 if s.lower() == g.lower():
#                     num += 1
#         # print('Comparing: {}, {}'.format(swords, gwords))
#         return num
#
#     def _search_report(self, sub_list, search):
#
#         if len(sub_list) == 0:
#             return None
#         #format of flatlist is: (name, level, address)
#         best = {'item':sub_list[0], 'matches':0}
#         for item in sub_list:
#             match = self._num_matches(item[0], search)
#             if match > best['matches']:
#                 best['item'] = item
#                 best['matches'] = match
#         return best['item']
#
#     def _get_sublist(self, statement, root_item):
#         '''
#         root item should be an address
#         :param statement:
#         :param root_item:
#         :return:
#         '''
#         check_list = self._formats[statement]['flatlist']
#         valid_items = []
#         for item in check_list:
#             if root_item in item[2]:
#                 valid_items.append(item)
#         return valid_items
#
#     def _get_item(self, statement, context, address):
#         exec_str = 'self.reports[\'{}\'][\'{}\']{}'.format(statement, context, address)
#         ret = eval(exec_str)
#         return ret
#
#     def _word_split(self, gaapitem):
#         camel = re.compile('[A-Z][^A-Z]*')
#         gitem = gaapitem.split(sep=':')[1]
#         gwords = re.findall(camel, gitem)
#         return gwords
#
#     def _address_of(self, statement, items):
#         def safe_index(list, value, default):
#             try:
#                 return list.index(value)
#             except ValueError:
#                 return default
#         format_items = self._formats[statement]['flatlist']
#         potential_items = [x[0] for x in format_items]
#         # [print(x) for x in items]
#         # print(statement)
#         # for f in potential_items:
#         #     print(f)
#         # print(len(potential_items))
#         # if len(potential_items) == 0:
#         #     print(json.dumps(self._formats, indent=2))
#         ind = 0
#         sitems = items
#         if type(items) != type([]):
#             sitems = [items]
#         for i in sitems:
#             if i in potential_items:
#                 ind = potential_items.index(i)
#             else:
#                 best = {'item': None, 'matches': 0}
#                 # print(statement)
#                 for d in potential_items:
#                     mach = self._num_matches(d, i)
#                     if mach > best['matches']:
#                         # print(i, item)
#                         best['item'] = d
#                         best['matches'] = mach
#                 # ind = potential_items.index(best['item'])
#                 ind = safe_index(potential_items, best['item'], None)
#
#             #find the best item
#
#         return format_items[ind][2]
#
#     def search(self, search_string, statement='balancesheet',  context=None, base=''):
#         '''
#         get a value from somewhere given a search string
#         :param search_string:
#         :param context:
#         :return:
#         '''
#         base_str = base
#         stat = statement
#         search = search_string.split()
#         search = [x.lower() for x in search]
#         valid = self._get_sublist(stat, base_str)
#         address = self._search_report(valid, search)[2]
#         context = self._defaults[stat]['ref']
#         return self._get_item(stat, context, address)
#
#     def liability(self, search_string='liabilities', context=None):
#         return self.search(search_string, statement='balancesheet', context=context, base=self.roots['balancesheet']['liabilities'])
#
#     def current_liability(self, search_string='liabilities current', context=None):
#         return self.search(search_string, statement='balancesheet', context=context, base=self.roots['balancesheet']['currentliabilities'])
#
#     def asset(self, search_string='assets', context=None):
#         return self.search(search_string, statement='balancesheet', context=context, base=self.roots['balancesheet']['assets'])
#
#     def current_assets(self, search_string='assets current', context=None):
#         return self.search(search_string, statement='balancesheet', context=context, base=self.roots['balancesheet']['currentassets'])
#
#     def equity(self, search_string='stock holders equity', context=None):
#         return self.search(search_string, statement='balancesheet', context=context, base=self.roots['balancesheet']['stockholdersequity'])
#
#     def cash(self, search_string='cash', context=None):
#         return self.search(search_string, statement='balancesheet', context=context, base=self.roots['balancesheet']['cash'])
#
#     def cash_from_operations(self, search_string='net cash provided by used in operating activities', context=None):
#         return self.search(search_string, statement='cashflows', context=context, base=self.roots['cashflows']['operating'])
#
#     def cash_from_financing(self, search_string='net cash provided by used in financing activities', context=None):
#         return self.search(search_string, statement='cashflows', context=context, base=self.roots['cashflows']['financing'])
#
#     def cash_from_investing(self, search_string='net cash provided by used in investing activities', context=None):
#         return self.search(search_string, statement='cashflows', context=context, base=self.roots['cashflows']['investing'])
#
#     def cash_change(self, search_string='cash cashcquivalents restricted cash and restricted cash equivalents period increase decrease including exchange rate effect',
#                     context=None):
#         return self.search(search_string, statement='cashflows', context=context, base=self.roots['cashflows']['cashflow'])
#
#     def net_income(self, search_string='net income loss',
#                    context=None):
#         return self.search(search_string, statement='operations', context=context, base=self.roots['operations']['net'])
#
#     def gross_profit(self, search_string='gross profit margin',
#                      context=None):
#         return self.search(search_string, statement='operations', context=context, base=self.roots['operations']['gross'])
#
#
#     def sum_items(self, statement, context, root, exclude_list):
#         '''
#         sums the items of a dict tree
#         exclude should be either a single item, or an item that has its own sub items
#         root is where to start
#         :param root:
#         :return:
#         '''
#         sum = 0
#         item_list = self._get_sublist(statement, root)
#         for item in item_list:
#             exclude = False
#             for e in exclude_list:
#                 if type(e) == type(re.compile('')):
#                     if re.match(e, item[2]):
#                         exclude = True
#                 elif e in item[2]:
#                     exclude = True
#             if not exclude:
#                 num = self._get_item(statement, context, item[2])['value']
#                 sum += float(num)
#         return str(sum)
#
#     def _fix_liability(self):
#         '''
#         Calculate Total Liabilities if it was not included
#         :return:
#         '''
#         laddress = self._address_of('balancesheet', 'us-gaap:Liabilities')
#         contexts = self._contexts['balancesheet'].keys()
#         for context in contexts:
#             liability_value = self.sum_items('balancesheet', context, laddress, [])
#             exec_str = 'self.reports[\'{}\'][\'{}\']{}[\'value\'] = {}'.format('balancesheet', context, laddress, liability_value)
#             exec(exec_str)
#         return



'''
How to search the report?

Give an item name, sometimes I want to search a smaller list, sometimes I want to search the whole
thing. To really make use of the structure that I've captured, I should just make one generic search function for
the flatlist, and then a search of some category can be done by giving a subset of the
'''

'''
"['us-gaap:LiabilitiesAndStockholdersEquity']"
"['us-gaap:Assets']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:Liabilities']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:CommitmentsAndContingencies']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:StockholdersEquity']"
"['us-gaap:Assets']['items']['us-gaap:AssetsCurrent']"
"['us-gaap:Assets']['items']['us-gaap:PropertyPlantAndEquipmentNet']"
"['us-gaap:Assets']['items']['us-gaap:OperatingLeaseRightOfUseAsset']"
"['us-gaap:Assets']['items']['us-gaap:LongTermInvestments']"
"['us-gaap:Assets']['items']['us-gaap:Goodwill']"
"['us-gaap:Assets']['items']['us-gaap:FiniteLivedIntangibleAssetsNet']"
"['us-gaap:Assets']['items']['us-gaap:OtherAssetsNoncurrent']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:Liabilities']['items']['us-gaap:LiabilitiesCurrent']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:Liabilities']['items']['us-gaap:LongTermDebtNoncurrent']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:Liabilities']['items']['us-gaap:AccruedIncomeTaxesNoncurrent']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:Liabilities']['items']['us-gaap:ContractWithCustomerLiabilityNoncurrent']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:Liabilities']['items']['us-gaap:DeferredIncomeTaxLiabilitiesNet']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:Liabilities']['items']['us-gaap:OperatingLeaseLiabilityNoncurrent']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:Liabilities']['items']['us-gaap:OtherLiabilitiesNoncurrent']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:StockholdersEquity']['items']['us-gaap:CommonStocksIncludingAdditionalPaidInCapital']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:StockholdersEquity']['items']['us-gaap:RetainedEarningsAccumulatedDeficit']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:StockholdersEquity']['items']['us-gaap:AccumulatedOtherComprehensiveIncomeLossNetOfTax']"
"['us-gaap:Assets']['items']['us-gaap:AssetsCurrent']['items']['us-gaap:CashCashEquivalentsAndShortTermInvestments']"
"['us-gaap:Assets']['items']['us-gaap:AssetsCurrent']['items']['us-gaap:AccountsReceivableNetCurrent']"
"['us-gaap:Assets']['items']['us-gaap:AssetsCurrent']['items']['us-gaap:InventoryNet']"
"['us-gaap:Assets']['items']['us-gaap:AssetsCurrent']['items']['us-gaap:OtherAssetsCurrent']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:Liabilities']['items']['us-gaap:LiabilitiesCurrent']['items']['us-gaap:AccountsPayableCurrent']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:Liabilities']['items']['us-gaap:LiabilitiesCurrent']['items']['us-gaap:LongTermDebtCurrent']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:Liabilities']['items']['us-gaap:LiabilitiesCurrent']['items']['us-gaap:EmployeeRelatedLiabilitiesCurrent']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:Liabilities']['items']['us-gaap:LiabilitiesCurrent']['items']['us-gaap:AccruedIncomeTaxesCurrent']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:Liabilities']['items']['us-gaap:LiabilitiesCurrent']['items']['us-gaap:ContractWithCustomerLiabilityCurrent']"
"['us-gaap:LiabilitiesAndStockholdersEquity']['items']['us-gaap:Liabilities']['items']['us-gaap:LiabilitiesCurrent']['items']['us-gaap:OtherLiabilitiesCurrent']"
"['us-gaap:Assets']['items']['us-gaap:AssetsCurrent']['items']['us-gaap:CashCashEquivalentsAndShortTermInvestments']['items']['us-gaap:CashAndCashEquivalentsAtCarryingValue']"
"['us-gaap:Assets']['items']['us-gaap:AssetsCurrent']['items']['us-gaap:CashCashEquivalentsAndShortTermInvestments']['items']['us-gaap:ShortTermInvestments']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInFinancingActivities']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInInvestingActivities']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:EffectOfExchangeRateOnCashAndCashEquivalents']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']['items']['us-gaap:NetIncomeLoss']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']['items']['us-gaap:DepreciationAmortizationAndOther']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']['items']['us-gaap:ShareBasedCompensation']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']['items']['us-gaap:GainLossOnInvestmentsAndDerivativeInstruments']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']['items']['us-gaap:DeferredIncomeTaxExpenseBenefit']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']['items']['us-gaap:IncreaseDecreaseInAccountsReceivable']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']['items']['us-gaap:IncreaseDecreaseInInventories']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']['items']['us-gaap:IncreaseDecreaseInOtherCurrentAssets']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']['items']['us-gaap:IncreaseDecreaseInOtherNoncurrentAssets']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']['items']['us-gaap:IncreaseDecreaseInAccountsPayable']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']['items']['us-gaap:IncreaseDecreaseInContractWithCustomerLiability']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']['items']['us-gaap:IncreaseDecreaseInAccruedIncomeTaxesPayable']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']['items']['us-gaap:IncreaseDecreaseInOtherCurrentLiabilities']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInOperatingActivities']['items']['us-gaap:IncreaseDecreaseInOtherNoncurrentLiabilities']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInFinancingActivities']['items']['us-gaap:RepaymentsOfDebtMaturingInMoreThanThreeMonths']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInFinancingActivities']['items']['us-gaap:ProceedsFromIssuanceOfCommonStock']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInFinancingActivities']['items']['us-gaap:PaymentsForRepurchaseOfCommonStock']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInFinancingActivities']['items']['us-gaap:PaymentsOfDividendsCommonStock']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInFinancingActivities']['items']['us-gaap:ProceedsFromPaymentsForOtherFinancingActivities']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInInvestingActivities']['items']['us-gaap:PaymentsToAcquirePropertyPlantAndEquipment']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInInvestingActivities']['items']['us-gaap:AcquisitionsNetOfCashAcquiredAndPurchasesOfIntangibleAndOtherAssets']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInInvestingActivities']['items']['us-gaap:PaymentsToAcquireInvestments']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInInvestingActivities']['items']['us-gaap:ProceedsFromMaturitiesPrepaymentsAndCallsOfAvailableForSaleSecurities']"
"['us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect']['items']['us-gaap:NetCashProvidedByUsedInInvestingActivities']['items']['us-gaap:ProceedsFromInvestments']"
"['us-gaap:NetIncomeLoss']"
"['us-gaap:NetIncomeLoss']['items']['us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments']"
"['us-gaap:NetIncomeLoss']['items']['us-gaap:IncomeTaxExpenseBenefit']"
"['us-gaap:NetIncomeLoss']['items']['us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments']['items']['us-gaap:OperatingIncomeLoss']"
"['us-gaap:NetIncomeLoss']['items']['us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments']['items']['us-gaap:NonoperatingIncomeExpense']"
"['us-gaap:NetIncomeLoss']['items']['us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments']['items']['us-gaap:OperatingIncomeLoss']['items']['us-gaap:GrossProfit']"
"['us-gaap:NetIncomeLoss']['items']['us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments']['items']['us-gaap:OperatingIncomeLoss']['items']['us-gaap:ResearchAndDevelopmentExpense']"
"['us-gaap:NetIncomeLoss']['items']['us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments']['items']['us-gaap:OperatingIncomeLoss']['items']['us-gaap:SellingAndMarketingExpense']"
"['us-gaap:NetIncomeLoss']['items']['us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments']['items']['us-gaap:OperatingIncomeLoss']['items']['us-gaap:GeneralAndAdministrativeExpense']"
"['us-gaap:NetIncomeLoss']['items']['us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments']['items']['us-gaap:OperatingIncomeLoss']['items']['us-gaap:GrossProfit']['items']['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax']"
"['us-gaap:NetIncomeLoss']['items']['us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments']['items']['us-gaap:OperatingIncomeLoss']['items']['us-gaap:GrossProfit']['items']['us-gaap:CostOfGoodsAndServicesSold']"
"['us-gaap:CommonStockSharesOutstanding']"
"['us-gaap:CommonStockSharesAuthorized']"
"['us-gaap:AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment']"
"['us-gaap:AllowanceForDoubtfulAccountsReceivableCurrent']"
'''