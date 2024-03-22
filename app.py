from flask import Flask, render_template
import os
import whisper

from config.log import logger
from config.frp import start_frp
from dao.db import TableInit
import argparse 

from web.audio import bp_audio
from web.video import bp_video
from web.tts import bp_tts

app = Flask(__name__)
# 音频模块
app.register_blueprint(bp_audio)
# 视频模块
app.register_blueprint(bp_video)
# tts语音模块
app.register_blueprint(bp_tts)

#=============================全局参数配置===================================
# 设置上传保存路径
app.config['UPLOAD_FOLDER'] = './upload'
app.config['AUDIO_GENERATE'] = './audio-generate'
app.config['DB_FILE_PATH'] = './dao/db/media.db'

model_size_options = ['tiny', 'base', 'small', 'medium', 'large']


def init_model(size):
    for model_size in model_size_options:
        if size == model_size:
            whisper.load_model(model_size)


def init_db():
    db_path = app.config['DB_FILE_PATH']
    if not os.path.exists(db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        open(db_path, 'a').close()
    table_init = TableInit(db_path)
    table_init.clear_tables()
    table_init.execute_create_tables()
    

@app.route('/')
def hello():
    return render_template('upload.html')


@app.route('/login')
def login():
    return 'login'


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument("-frp", type=bool, default=False,help="open frp")
    parser.add_argument("-frp-config-path", type=str, default='',help="frp config paht")
    parser.add_argument('-dbinit', type=bool, default=False, help="clear db, start new project")
    parser.add_argument('-model', type=str, default='large', help="load whisper model")
    parser.add_argument('--processes', type=int, default=0, help="cpu_processes")
    args, _ = parser.parse_known_args()

    if args.dbinit:
        logger.info(f'init db: {True}')
        init_db()
    if args.frp:
        frp_config = args.get('frp-config-path', '')
        start_frp(frp_config)
    if args.model:
        init_model(args.model)
    app.run(host='0.0.0.0', port=9081)
    
    
    