#!/usr/bin/python

import sqlite3
import datetime as dt
import os
import sys
from pathlib import Path

def insert_user(user_info):
    os.chdir("/home/iu98/pneumo_page")
    conn = sqlite3.connect(str("pneumo_service.db"))
    c = conn.cursor()
    query=f"SELECT user_key FROM user WHERE user_key = '{user_info['user_key']}'"
    c.execute(query)
    num=c.fetchall()
    if(len(num)==0):
        x=dt.datetime.now()
        date=x.strftime("%A %d. %B %Y %H:%M:%S")
        query=f"INSERT INTO user VALUES ('{user_info['user_key']}', '{user_info['email']}', '{user_info['name']}', '{date}')"
        print("insert new user")
        c.execute(query)
        if not(os.path.exists("./user/"+user_info['user_key'])):
            os.system("mkdir ./user/"+user_info['user_key'])
            print("make ./user/"+user_info['user_key'])
        conn.commit()
        conn.close()


def insert_job(user_info,job_info):
    state="queue"
    os.chdir("/home/iu98/pneumo_page")
    conn = sqlite3.connect(str("pneumo_service.db"))
    c = conn.cursor()
    c.execute(f"SELECT job_num FROM job WHERE user_key='{user_info['user_key']}' ORDER BY job_num DESC LIMIT 1")
    num=c.fetchall()
    if num==[]:
        job_num=1
    else:
        job_num=num[0][0]+1
    x=dt.datetime.now()
    date=x.strftime("%A %d. %B %Y %H:%M:%S")
    c.executemany('INSERT INTO job VALUES (?,?,?,?,?,?,?)',
                  [(user_info["user_key"],user_info["username"],job_num,job_info["jobname"],str(job_info["file1"]+"|"+job_info["file2"]),state,date)])
    conn.commit()
    conn.close()

def read_user_job(user_key):
    os.chdir("/home/iu98/pneumo_page")
    conn = sqlite3.connect(str("pneumo_service.db"))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f"SELECT * FROM job WHERE user_key ='{user_key}'")
    tb=c.fetchall()
    return tb

def read_job_num(user_key):
    os.chdir("/home/iu98/pneumo_page")
    conn = sqlite3.connect(str("pneumo_service.db"))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f"SELECT job_num FROM job WHERE user_key='{user_key}' ORDER BY job_num DESC LIMIT 1")
    num=c.fetchall()
    if num==[]:
        job_num=1
    else:
        job_num=num[0][0]+1
    return job_num

def update_db(user_key,job_key,state):
    os.chdir("/home/iu98/pneumo_page")
    conn = sqlite3.connect(str("pneumo_service.db"))
    c = conn.cursor()
    c.execute("UPDATE job SET state = ? WHERE user_key = ? and job_num = ?",(state,user_key,job_key))
    conn.commit()
    conn.close()

def read_db_row(user_key,job_key):
    os.chdir("/home/iu98/pneumo_page")
    conn = sqlite3.connect(str("pneumo_service.db"))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    query=f"SELECT * FROM job WHERE user_key = '{str(user_key)}' and job_num = {int(job_key)}"
    print(query)
    c.execute(query)
    tb=c.fetchall()
    cols = [column[0] for column in c.description]
    return tb, cols

def read_user_db(user_key):
    os.chdir("/home/iu98/pneumo_page")
    conn = sqlite3.connect(str("pneumo_service.db"))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f"SELECT date FROM user WHERE user_key ='{user_key}'")
    tb=c.fetchone()
    return tb

def is_joined(user_key):
    os.chdir("/home/iu98/pneumo_page")
    conn = sqlite3.connect(str("pneumo_service.db"))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f"SELECT * FROM user WHERE user_key ='{user_key}'")
    tb=c.fetchone()
    if tb==None:
        return False
    else:
        return True
    
def delete_user_job(user_key,job_key):
    os.chdir("/home/iu98/pneumo_page")
    conn = sqlite3.connect(str("pneumo_service.db"))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f"DELETE FROM job WHERE user_key ='{user_key}' AND job_num = {job_key}")
    conn.commit()