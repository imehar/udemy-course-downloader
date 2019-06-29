import requests
from lxml import html
from bs4 import BeautifulSoup
from urllib.parse import unquote
import os
import math
from tqdm import tqdm, trange
import sys, getopt

headers = {
	    'Origin': 'www.udemy.com',
	    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0 Chrome/75.0.3770.100 ',
	    'Referer': 'https://www.udemy.com/join/login-popup/',
	    }

base_url = "https://www.udemy.com/"
login_url = base_url + "join/login-popup/"
subscribed_url = base_url + 'api-2.0/users/me/subscribed-courses'
asset_of_lec  = 'https://www.udemy.com/api-2.0/users/me/subscribed-courses/{0}/lectures/{1}'
course_info_url = 'https://www.udemy.com/api-2.0/courses/{0}/subscriber-curriculum-items/'

def login(session,email,password):
    params = (
        ('display_type', ['popup', 'popup']),
        ('locale', 'en_US'),
        ('next', 'https://www.udemy.com/'),
        ('ref', ''),
        ('response_type', 'json'),
        ('xref', ''),
    )
    response = session.get(login_url, headers=headers, params=params)
    tree = html.fromstring(response.content)
    _login_url = tree.xpath(".//form[@id='login-form']")[0].action
    soup = BeautifulSoup(response.content,'html.parser')
    inputs = soup.find_all('input')
    params = {}
    for i in inputs:
        if i['type']=='hidden' or i['type']=='submit':
            params[i['name']] = i['value']
    params['email'] = email
    params['password'] =password
    res = session.post(unquote(_login_url), data=params,headers=headers)
    access_token = res.cookies.get('access_token','')
    if access_token != '':
        print('You\'re in...')
    else:
        print('Error in login')
    client_id = res.cookies.get('client_id','')
    session.headers['authorization'] = "Bearer {0}".format(access_token)
    session.headers['client_id'] = client_id
    session.headers['x-udemy-authorization'] = "Bearer {0}".format(access_token)



def get_subscribed_courses(session):
    params = (
        ('fields/[course/]', '@min,visible_instructors,image_240x135,image_480x270,favorite_time,archive_time,completion_ratio,last_accessed_time,enrollment_time,is_practice_test_course,features,num_collections,published_title,buyable_object_type,most_recent_activity'),
        ('fields/[user/]', '@min'),
        ('ordering', 'most_recent_activity'),
        ('page', '1'),
        ('page_size', '8'),
        ('max_progress', '99.9'),
        ('is_archived', 'false'),
    )

    response = session.get(subscribed_url, params=params)
    subscribed_course_details = response.json()
    no_of_course = subscribed_course_details.get('count',0)
    course_id = []
    if no_of_course>0:
        for course in subscribed_course_details['results']:
            course_id.append([course['id'],course['title']])
    return course_id

def get_course_lecture_info(session,course_id):
    params = (
        ('page_size', '1400'),
        ('fields/[lecture/]', 'title,object_index,is_published,sort_order,created,asset,supplementary_assets,last_watched_second,is_free'),
        ('fields/[quiz/]', 'title,object_index,is_published,sort_order,type'),
        ('fields/[practice/]', 'title,object_index,is_published,sort_order'),
        ('fields/[chapter/]', 'title,object_index,is_published,sort_order'),
        ('fields/[asset/]', 'title,filename,asset_type,external_url,status,time_estimation'),
    )
    course_url = course_info_url.format(course_id)
    course = session.get(course_url, headers=headers, params=params)
    course_details = course.json().get('results')
    course_lec_id = []
    for course_detail in course_details:
        course_lec_id.append((course_detail['_class'],course_detail['id'],course_detail['title']))
    return course_lec_id


def get_lecture_assets(session,course_id,lecture_id):
    params = (
        ('fields[asset]', '@min,download_urls,external_url,slide_urls,status,time_estimation,stream_urls'),
        ('fields[course]','id,url,locale'),
        ('fields[lecture&=','@default,course,can_give_cc_feedback,can_see_cc_feedback_popup,download_url'),
    )
    assets_url = asset_of_lec.format(466000,7141990)
    response = session.get(assets_url, params=params)
    return response.json()



def download_asset(session,course_id,lecture,lesson_counter,directory=os.getcwd()):
    if lecture[0]=="lecture":
        asset_detail = get_lecture_assets(session,course_id,lecture[1])
        filename = lecture[2]
        urls = asset_detail.get('asset').get('download_urls',None)
        if urls ==None:
            urls = asset_detail.get('asset').get('stream_urls',None)
        url = urls['Video'][0]['file']
        ext = url.split('/')[-1].split('?')[0].split('.')[-1]
        vid_name = filename + '.'+  ext
        if not os.path.isfile(os.path.join(directory,str(lesson_counter)+"_"+vid_name)):
            tqdm.write(f'{filename} ')
            r = session.get(url, stream=True)
            total = r.headers.get('content-length')
            with open(os.path.join(directory,str(lesson_counter)+"_"+vid_name),'wb') as f:
                if total is None:
                    f.write(response.content)
                else:
                    total = int(total)
                    for chunk in tqdm(r.iter_content(chunk_size=1024), total=math.ceil(total//1024), unit='KB', unit_scale=True):
                        if chunk:
                            f.write(chunk)
                            f.flush()
                print('Finished ' + filename)
        else:
        	tqdm.write(f'{filename} already exists, skipping.')



def download_course(session,course_id,directory=os.getcwd()):
    if not os.path.isdir(os.path.join(directory,course_id[1])):
        os.makedirs(os.path.join(directory,course_id[1]))
    directory = os.path.join(directory,course_id[1])
    lectures = get_course_lecture_info(session,course_id[0])
    chapters = [chap for chap in lectures if chap[0]=='chapter']
    lesson_counter = 1
    chapters_dir = {}
    for i,chap in enumerate(chapters):
        chapters_dir[chap[2]] = os.path.join(directory,str(i+1)+"_"+chap[2])
    for i,lecture in enumerate(lectures):
        if lecture[0]=='chapter':
        	lesson_counter = 1
        	print("{0}/{1} Downloading... ".format(i,len(lectures)))
        	if not os.path.isdir(chapters_dir[lecture[2]]):
        		os.makedirs(chapters_dir[lecture[2]])
        	else:
        		tqdm.write(f'{lecture[2]} already exists, skipping.')
        	directory = chapters_dir[lecture[2]]                      
        else:
        	print("{0}/{1} Downloading... ".format(i,len(lectures)))
        	download_asset(session,course_id,lecture,lesson_counter,directory)
        	lesson_counter+=1
     		


def download_all_courses(session,directory=os.getcwd()):
    courses = get_subscribed_courses(session)
    for course in courses:
    	tqdm.write(f'\nDownloading course  {course[1]}')
    	download_course(session,course,directory)


def main(argv):

    email = None
    password = None
    directory = os.path.join(os.getcwd(),'udemy_courses')
    errorMessage = 'Usage: udemy-downloader.py -e <email> -p <password> [-d <directory> ]'

    # get the command line arguments/options
    try:
        opts, args = getopt.getopt(argv,"e:p:d:",["email=","pass=","directory="])
    except getopt.GetoptError:
        print(errorMessage)
        sys.exit(2)

    # hold the values of the command line options
    for opt, arg in opts:
        if opt in ('-e','--email'):
            email = arg
        elif opt in ('-p','--pass'):
            password = arg
        elif opt in ('-d','--directory'):
            directory = os.path.expanduser(arg) if '~' in arg else os.path.abspath(arg)
    if not os.path.isdir(directory):
    	os.makedirs(directory)
    
    session = requests.session()
    login(session,email,password)
    download_all_courses(session,directory)



if __name__ == "__main__":
	main(sys.argv[1:])