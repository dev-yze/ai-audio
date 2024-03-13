import sqlite3
from sqlite3 import Error
import time
import inspect
import json

class SQLiteDB:
    def __init__(self, db_file):
        """初始化SQLiteDB类的实例"""
        self.db_file = db_file
        self.conn = None

    def create_conn(self):
        """创建一个数据库连接"""
        try:
            self.conn = sqlite3.connect(self.db_file)
            return self.conn
        except Error as e:
            print(e)

    def create_dict_conn(self):
        try:
            self.conn = sqlite3.connect(self.db_file)
            self.conn.row_factory = sqlite3.Row
            return self.conn
        except Error as e:
            print(e)

    def close_conn(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def execute_sql(self, sql, params=None):
        """执行SQL语句"""
        if self.conn:
            try:
                cur = self.conn.cursor()
                if params:
                    cur.execute(sql, params)
                else:
                    cur.execute(sql)
                self.conn.commit()
                return cur
            except Error as e:
                print(e)

    def query(self, sql, params=None):
        """执行查询并返回结果"""
        if self.conn:
            cur = self.conn.cursor()
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            return cur.fetchall()

    def remove_table(self, table_name):
        """删除表格"""
        sql = f"DROP TABLE IF EXISTS {table_name}"
        self.execute_sql(sql)
        self.close_conn()


class TableInit:
    
    def __init__(self, db_file):
        """初始化SQLiteDB类的实例"""
        self.db = SQLiteDB(db_file=db_file)
        self.db.create_conn()

    def create_video_table(self):
         # 保存上传视频	
        create_video_table_sql = '''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                md5 TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        '''
        self.db.execute_sql(create_video_table_sql)

    def create_audio_table(self):
        create_audio_table_sql = '''
            CREATE TABLE IF NOT EXISTS audios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                md5 TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        '''
        self.db.execute_sql(create_audio_table_sql)

    def create_audio_cut_table(self):
        create_audio_cut_table_sql = '''
            CREATE TABLE IF NOT EXISTS audio_cuts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audio_main_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                md5 TEXT NOT NULL,
                trans_text TEXT,
                language TEXT,
                created_at TEXT NOT NULL
            )
        '''
        self.db.execute_sql(create_audio_cut_table_sql)


    def create_audio_text_segments_table(self):
        sql = '''
            CREATE TABLE IF NOT EXISTS audio_text_segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audio_id INTEGER NOT NULL,
                role TEXT,
                text_id INTEGER NOT NULL,
                seek INTEGER,
                start REAL,
                end REAL,
                text TEXT,
                tokens TEXT,
                temperature REAL, 
                avg_logprob REAL, 
                compression_ratio REAL, 
                no_speech_prob REAL,
                created_at TEXT NOT NULL
            )
        '''
        self.db.execute_sql(sql)


    def execute_create_tables(self):
        # 获取当前实例的所有成员
        members = inspect.getmembers(self, predicate=inspect.ismethod)
        # 遍历成员
        for name, method in members:
            # 如果成员是方法且不是 execute_create_tables 自身，则调用它
            if name.startswith('create_'):
                method()

        self.db.close_conn()

    def close_conn(self):
        self.db.close_conn()


'''
视频相关操作
'''
class VideoWrapper:
    def __init__(self, db_file):
        """初始化SQLiteDB类的实例"""
        self.db = SQLiteDB(db_file=db_file)

    def inser_video(self, file_name, file_path, md5):
        self.db.create_conn()
        insert_sql = '''
            INSERT INTO videos (file_name, file_path, md5, created_at) VALUES (?, ?, ?, ?)
        '''
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        rowid = self.db.execute_sql(insert_sql, (file_name, file_path, md5, timestamp))
        self.db.close_conn()
        return rowid

    def update_video(self, file_name, file_path, md5, id):
        self.db.create_conn()
        sql = '''
            UPDATE videos SET file_name = ?, file_path = ?, md5 = ? WHERE id = ?
        '''
        rowid = self.db.execute_sql(sql, (file_name, file_path, md5, id))
        self.db.close_conn()


    def find_video_by_id(self, id):
        if not id:
            return
        sql = "SELECT * FROM videos WHERE id = ?"
        self.db.create_dict_conn()
        result = self.db.query(sql, (id,))
        self.db.close_conn()
        return result


    def find_video_by_md5(self, md5):
        if not md5:
            return
        sql = "SELECT * FROM videos WHERE md5 = ?"
        self.db.create_dict_conn()
        result = self.db.query(sql, (md5,))
        self.db.close_conn()
        return result



    def find_video_by_filename(self, file_name):
        if not file_name:
            return
        sql = "SELECT * FROM videos WHERE file_name = ?"
        self.db.create_dict_conn()
        result = self.db.query(sql, (file_name,))
        self.db.close_conn()
        return result

    def del_by_id(self, id):
        if not id:
            return
        sql = "DELETE FROM videos WHERE id = ?"
        self.db.create_dict_conn()
        result = self.db.execute_sql(sql, (id,))
        self.db.close_conn()
        return result


    '''
    查询视频列表
    '''
    def list_video(self):
        sql = "SELECT * FROM videos"
        self.db.create_dict_conn()
        result = self.db.query(sql)
        self.db.close_conn()
        return result


    def close_conn(self):
        self.db.close_conn()


'''
音频相关数据库操作
'''
class AudioWrapper:
    def __init__(self, db_file):
        """初始化SQLiteDB类的实例"""
        self.db = SQLiteDB(db_file=db_file)

    '''
    插入音频
    '''
    def inser_audio(self, video_id, file_name, file_path, md5):
        self.db.create_conn()
        insert_sql = '''
            INSERT INTO audios (video_id, file_name, file_path, md5, created_at) VALUES (?, ?, ?, ?, ?)
        '''
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        rowid = self.db.execute_sql(insert_sql, (video_id, file_name, file_path, md5, timestamp))
        self.db.close_conn()
        return rowid

    def find_audio_by_id(self, id):
        if not id:
            return
        sql = "SELECT * FROM audios WHERE id = ?"
        self.db.create_dict_conn()
        result = self.db.query(sql, (id,))
        self.db.close_conn()
        return result
    

    def find_audio_by_md5(self, md5):
        if not md5:
            return
        sql = "SELECT * FROM audios WHERE md5 = ?"
        self.db.create_dict_conn()
        result = self.db.query(sql, (md5,))
        self.db.close_conn()
        return result



    def find_audio_by_filename(self, file_name):
        if not file_name:
            return
        sql = "SELECT * FROM audios WHERE file_name = ?"
        self.db.create_dict_conn()
        result = self.db.query(sql, (file_name,))
        self.db.close_conn()
        return result


    def find_audio_by_video_id(self, video_id):
        if not video_id:
            return
        sql = "SELECT * FROM audios WHERE video_id = ?"
        self.db.create_dict_conn()
        result = self.db.query(sql, (video_id,))
        self.db.close_conn()
        return result


    '''
    查询音频列表
    '''
    def list_audio(self):
        sql = "SELECT * FROM audios"
        self.db.create_dict_conn()
        result = self.db.query(sql)
        self.db.close_conn()
        return result

    def del_by_id(self, id):
        if not id:
            return
        sql = "DELETE FROM audios WHERE id = ?"
        self.db.create_dict_conn()
        result = self.db.execute_sql(sql, (id,))
        self.db.close_conn()
        return result

    def close_conn(self):
        self.db.close_conn()


'''
音频裁剪相关操作
'''
class AudioCutWrapper:
    def __init__(self, db_file):
        """初始化SQLiteDB类的实例"""
        self.db = SQLiteDB(db_file=db_file)

    def inser_audio_cut_init(self, id, audio_main_id, file_name, file_path, md5, created_at):
        self.db.create_conn()
        insert_sql = '''
            INSERT INTO audio_cuts (id, audio_main_id, file_name, file_path, md5, created_at) VALUES (?, ?, ?, ?, ?, ?)
        '''
        rowid = self.db.execute_sql(insert_sql, (id, audio_main_id, file_name, file_path, md5, created_at))
        self.db.close_conn()
        return rowid

    def inser_audio_cut(self, audio_main_id, file_name, file_path, md5):
        self.db.create_conn()
        insert_sql = '''
            INSERT INTO audio_cuts (audio_main_id, file_name, file_path, md5, created_at) VALUES (?, ?, ?, ?, ?)
        '''
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        rowid = self.db.execute_sql(insert_sql, (audio_main_id, file_name, file_path, md5, timestamp))
        self.db.close_conn()
        return rowid

    def update_audio_cut_text(self, id, text, language):
        self.db.create_conn()
        insert_sql = '''
            UPDATE audio_cuts SET trans_text = ?, language = ? WHERE id = ? 
        '''
        rowid = self.db.execute_sql(insert_sql, (text, language,id,))
        self.db.close_conn()
        return rowid

    def find_audio_cut_by_id(self, id):
        if not id:
            return
        sql = "SELECT * FROM audio_cuts WHERE id = ?"
        self.db.create_dict_conn()
        result = self.db.query(sql, (id,))
        self.db.close_conn()
        return result


    def find_audio_cut_by_md5(self, md5):
        if not md5:
            return
        sql = "SELECT * FROM audio_cuts WHERE md5 = ?"
        self.db.create_dict_conn()
        result = self.db.query(sql, (md5,))
        self.db.close_conn()
        return result



    def find_audio_cut_by_filename(self, file_name):
        if not file_name:
            return
        sql = "SELECT * FROM audio_cuts WHERE file_name = ?"
        self.db.create_dict_conn()
        result = self.db.query(sql, (file_name,))
        self.db.close_conn()
        return result


    '''
    根据主音频查询剪辑列表
    '''
    def list_audio_cut_by_ami(self, audio_main_id):
        sql = "SELECT * FROM audio_cuts WHERE audio_main_id = ?"
        self.db.create_dict_conn()
        result = self.db.query(sql, (audio_main_id,))
        self.db.close_conn()
        return result

    '''
    查询音频剪辑列表
    '''
    def list_audio_cut(self):
        sql = "SELECT * FROM audio_cuts"
        self.db.create_dict_conn()
        result = self.db.query(sql)
        self.db.close_conn()
        return result

    
    def del_by_id(self, id):
        if not id:
            return
        sql = "DELETE FROM audio_cuts WHERE id = ?"
        self.db.create_dict_conn()
        result = self.db.execute_sql(sql, (id,))
        self.db.close_conn()
        return result


    def close_conn(self):
        self.db.close_conn()


'''
音频文本区段
'''
class AudioTextSegmentsWrapper:
    def __init__(self, db_file):
        """初始化SQLiteDB类的实例"""
        self.db = SQLiteDB(db_file=db_file)


    def inser_audio_text_segments(self, audio_id, data):
        self.db.create_conn()
        insert_sql = '''
            INSERT INTO audio_text_segments (
                audio_id, text_id, 
                seek, start, end, 
                text, tokens,
                temperature,
                avg_logprob, compression_ratio,no_speech_prob,
                created_at
            ) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ? ,?, ?, ?, ?)
        '''
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        rowid = self.db.execute_sql(insert_sql, (audio_id, data['id'], 
                                                data['seek'], data['start'], data['end'], 
                                                data['text'], json.dumps(data['tokens']),
                                                data['temperature'],
                                                data['avg_logprob'], data['compression_ratio'], data['no_speech_prob'], 
                                                 timestamp,))
        self.db.close_conn()
        return rowid

    def find_by_id(self, id):
        sql = "SELECT * FROM audio_text_segments WHERE id = ?"
        self.db.create_dict_conn()
        result = self.db.query(sql, (id,))
        self.db.close_conn()
        return result

    def list_by_audio_id(self, audio_id):
        if not audio_id:
            return
        sql = "SELECT * FROM audio_text_segments WHERE audio_id = ? ORDER BY text_id ASC"
        self.db.create_dict_conn()
        result = self.db.query(sql, (audio_id,))
        self.db.close_conn()
        return result

    def del_by_audio_id(self, audio_id):
        if not id:
            return
        sql = "DELETE FROM audio_text_segments WHERE audio_id = ?"
        self.db.create_dict_conn()
        result = self.db.query(sql, (audio_id,))
        self.db.close_conn()
        return result

    def del_by_id(self, id):
        if not id:
            return
        sql = "DELETE FROM audio_text_segments WHERE id = ?"
        self.db.create_dict_conn()
        result = self.db.execute_sql(sql, (id,))
        self.db.close_conn()
        return result


    def close_conn(self):
        self.db.close_conn()

def test():
    db = SQLiteDB('./db/example.db')

    # 创建连接
    db.create_conn()

    # 创建表
    create_table_sql = '''CREATE TABLE IF NOT EXISTS stocks
                          (date text, trans text, symbol text, qty real, price real)'''
    db.execute_sql(create_table_sql)

    # 插入数据
    insert_sql = "INSERT INTO stocks VALUES (?, ?, ?, ?, ?)"
    db.execute_sql(insert_sql, ('2006-01-05', 'BUY', 'RHAT', 100, 35.14))

    # 查询数据
    select_sql = "SELECT * FROM stocks WHERE trans=?"
    rows = db.query(select_sql, ('BUY',))
    for row in rows:
        print(row)

    # 关闭连接
    db.close_conn()

def remove_table(dbfile, table_name):
    db = SQLiteDB(dbfile)
    # 创建连接
    db.create_conn()
    db.execute_sql(f"DROP TABLE IF EXISTS {table_name}")
    db.close_conn


def alter_table(dbfile):
    remove_table(dbfile, '')
    # audioCutWrapper = AudioCutWrapper(dbfile)
    # audio_cut_data_list = audioCutWrapper.list_audio_cut()
    # audio_cut_data_list = [dict(item) for item in audio_cut_data_list]

    # remove_table(dbfile, 'audio_cuts')

    table_init = TableInit(dbfile)
    table_init.create_audio_text_segments_table()
    table_init.close_conn()
    
    # audioCutWrapper1 = AudioCutWrapper(dbfile)
    # for item in audio_cut_data_list:
        # result = audioCutWrapper1.inser_audio_cut_init(item['id'], 
        #                                      item['audio_main_id'],
        #                                      item['file_name'],
        #                                      item['file_path'],
        #                                      item['md5'],
        #                                      item['created_at']
        #                                      )
        # print(result)

    
    # db = SQLiteDB(dbfile)
     # 创建连接
    # db.create_conn()
    # db.execute_sql(f"ALTER TABLE audio_cuts EXISTS {table_name}")
    # db.close_conn


# 使用SQLiteDB类
if __name__ == "__main__":

    db_file = './db/media.db'
    # alter_table(db_file)

    # remove_table('./db/example.db', 'videos')
    # remove_table('./db/example.db', 'audios')
    # remove_table('./db/example.db', 'audio_cuts')
    # remove_table('./db/example.db', 'stocks')
    
    # tableinit = TableInit(db_file=db_file)
    # tableinit.execute_create_tables()

    # video_wrapper = VideoWrapper(db_file=db_file)
    # video_wrapper.inser_video('a.mp4', './b/a.mp4', 'f45fewe')
    # video_wrapper.inser_video('b.mp4', './b/b.mp4', 'f48fewe')
    # video_wrapper.inser_video('c.mp4', '.c/c.mp4', 'fsfsfew')
    # results = video_wrapper.find_video_by_filename('c.mp4')
    # print('find_video_by_filename result:')
    # for row in results:
    #     print(dict(row))
    # results = video_wrapper.find_video_by_md5('f48fewe')
    # print('find_video_by_md5 result:')
    # for row in results:
    #     print(dict(row))
    # video_wrapper.del_by_id(1)
    
    # results = video_wrapper.list_video()
    # print('list_video result:')
    # for row in results:
    #     print(dict(row))



    # audio_wrapper = AudioWrapper(db_file=db_file)
    # audio_wrapper.del_by_id(15)
    # audio_wrapper.del_by_id(16)
    # audio_wrapper.inser_audio(1, 'a.wav', './b/a.wav', 'f4jfewe')
    # audio_wrapper.inser_audio(2, 'b1.wav', './b/b.wav', 'fa8ffewe')
    # audio_wrapper.inser_audio(2, 'b2.wav', '.c/c.wav', 'fsfsfseew')
    # results = audio_wrapper.find_audio_by_filename('a.wav')
    # print('find_audio_by_filename result:')
    # for row in results:
    #     print(dict(row))
    # results = audio_wrapper.find_audio_by_md5('fa8ffewe')
    # print('find_audio_by_md5 result:')
    # for row in results:
    #     print(dict(row))
    
    # results = audio_wrapper.list_audio()
    # print('list_audio result:')
    # for row in results:
    #     print(dict(row))


    # audio_cut_wrapper = AudioCutWrapper(db_file=db_file)
    # audio_cut_wrapper.inser_audio_cut(1, 'a.wav', './b/a.wav', 'f4jfewe')
    # audio_cut_wrapper.inser_audio_cut(2, 'b.wav', './b/b.wav', 'fa8ffewe')
    # audio_cut_wrapper.inser_audio_cut(2, 'c.wav', '.c/c.wav', 'fsfsfseew')
    # results = audio_cut_wrapper.find_audio_cut_by_filename('a.wav')
    # print('find_audio_cut_by_filename result:')
    # for row in results:
    #     print(dict(row))
    # results = audio_cut_wrapper.find_audio_cut_by_md5('fa8ffewe')
    # print('find_audio_cut_by_md5 result:')
    # for row in results:
    #     print(dict(row))
    
    # results = audio_cut_wrapper.list_audio_cut()
    # print('list_audio_cut result:')
    # for row in results:
    #     print(dict(row))

    