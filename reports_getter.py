#!/Users/Jon/anaconda3/envs/trading/bin/python3
from bs4 import BeautifulSoup
from requests import Session
import sys
import os

'''
The url given should be that of the page that contains the data files, just give it that, and then read off the hfrefs
'''
base = 'https://www.sec.gov'

if __name__ == '__main__':
	ses = Session()
	text = None
	# with open('./msftdata/example.html', 'r') as f:
	# 	text = f.read()
	req = ses.get(sys.argv[1])
	text = req.text
	soup = BeautifulSoup(text, 'lxml')
	tags = soup.find_all()
	data_files = None
	# for i in range(0, len(tags)):
	# 	print("{} : {}".format(i, tags[i]))
	for tag in tags:
		if tag.find('table', {'class':'tableFile', 'summary':'Data Files'}):
			data_files = tag
	rows = data_files.find_all('a')
	files = []
	group_tags = soup.find('div', {'class':"formContent"}).find_all('div')
	fdate = None

	for i in range(len(group_tags)):
		if group_tags[i].text == 'Filing Date':
			fdate = group_tags[i+1].text
			break
	fdate = fdate.replace('-', '')
	for row in rows:
		files.append(row.attrs['href'])
	files = [base+x for x in files]
	ticker = files[0].split(sep='/')[-1].split(sep='-')[0]
	outbase = os.getcwd() + '/' + fdate + ticker
	if not os.path.exists(outbase):
		os.mkdir(outbase)

	os.chdir(outbase)
	outbase += '/'
	for file in files:
		outname = file.split(sep='/')[-1]
		req = ses.get(file)
		with open(outname, mode='w') as f:
			f.write(req.text)
	print('All done')
