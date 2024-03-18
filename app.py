from flask import Flask, render_template, request, redirect, url_for, send_file, Response, stream_with_context
import os
import whisper
from gtts import gTTS
from datetime import datetime
import re

from config import logger
from frp import start_frp

from media import allowed_file, convert_video_sys, mp4_to_audio, extract_audio, extract_wav_audio
from db import TableInit, VideoWrapper, AudioWrapper, AudioCutWrapper, AudioTextSegmentsWrapper
from vo import ApiResponse
from secret import md5_str, md5_file
import sys
import argparse 

app = Flask(__name__)


#=============================全局参数配置===================================
# 设置上传保存路径
app.config['UPLOAD_FOLDER'] = './upload'
app.config['AUDIO_GENERATE'] = './audio-generate'
app.config['DB_FILE_PATH'] = './db/media.db'

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


@app.route('/uploadaudio', methods=['POST'])
def upload_audio():
    file = request.files['file']

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)

    if os.path.exists(filepath):
            # 如果文件已经存在，就删除
            #os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
        return ApiResponse(-1, '文件已存在', None).to_json()
        # 检查文件类型是否允许上传
    if file and allowed_file(file.filename):
        # 保存文件到指定路径
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
        return ApiResponse(200, '文件上传成功', None).to_json()
        # 重定向到上传成功页面，并传递文件名参数
        # return redirect(url_for('SUCCESS', filename=file.filename))
    else:
        # 返回上传失败的提示信息
        return ApiResponse(-1, '不支持上传格式，目前只支持mp3', None).to_json()



@app.route('/audio2text', methods=['POST'])
def audioToText(language='zh'):
    
    file = request.files['file']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)

    if os.path.exists(filepath):
        # 如果文件已经存在，就删除
        os.remove(filepath)
        
    if file and allowed_file(file.filename):
         # 保存文件到指定路径
        file.save(filepath)
        
        initial_prompt = ''
        lan = request.form.get('lan')
        model_size = request.form.get('model')

        if not lan:
            lan = 'en'
        if lan == 'zh':
            initial_prompt = '以下是普通话句子'
        if not model_size:
            model_size = 'medium'
            
        # 加载模型
        model = whisper.load_model(model_size)
        
        result = model.transcribe(filepath, language=lan, initial_prompt=initial_prompt)
        return ApiResponse(200, 'SUCCESS', result['text']).to_json()
    
    else:
        # 返回上传失败的提示信息
        return ApiResponse(-1, '不支持上传格式，目前只支持mp3', None).to_json()



@app.route('/text2audio', methods=['POST'])
def textToAudio():
    data = request.json
    logger.info(data)
    text = data.get('data')
    lan = data.get('lan')
    filename = data.get('filename')
    if not filename:
        filename = md5_str(text)
    tts = gTTS(text=text, lang=lan)
    timestamp = datetime.now().timestamp()
    filepath = os.path.join(app.config['AUDIO_GENERATE'], filename + '_' + str(int(timestamp)) + '.mp3')
    tts.save(filepath)
    return send_file(filepath, mimetype='audio/mp3')

    
@app.route('/video/md5/<md5>')
def find_video(md5):
     video_wrapper = VideoWrapper(app.config['DB_FILE_PATH'])
     results = video_wrapper.find_video_by_md5(md5=md5)
     if results and len(results) > 1:
         return ApiResponse(200, "SUCCESS", dict(results[0])).to_json()
     return ApiResponse(200, "EMPTY", None).to_json()



@app.route('/video/list', methods=['POST'])
def list_video():
    video_wrapper = VideoWrapper(app.config['DB_FILE_PATH'])
    results = video_wrapper.list_video()
    results = [dict(item) for item in results]
    return ApiResponse(200, "SUCCESS", results).to_json()



# 上传视频
@app.route('/upload_video', methods=['POST'])
def uploadVideo():
    '''
        上传视频
        chunk: 分片文件
        cur: 当前分片索引
        total: 分片大小
        cmd5: 分片文件md5
        md5: 文件md5
        filename: 分片文件名称
    '''
    chunk = request.files['chunk']
    cur = int(request.form.get('cur'))
    total = int(request.form.get('total'))
    cmd5 = request.form.get('cmd5')
    md5 = request.form.get('md5')
    filename = request.form.get('filename')
    logger.info(f'cur={cur},total={total},cmd5={cmd5},md5={md5},filename={filename}')

    # 参数校验
    if not chunk:
        return ApiResponse(-1, '文件不存在', None).to_json()

    video_wrapper = VideoWrapper(app.config['DB_FILE_PATH'])
    # 检查文件是否已经存在
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        # return ApiResponse(-1, '文件已经存在', None).to_json()

    # 保存分片文件，临时存在上传路径/temp/md5
    chunk_dir_path = os.path.join(app.config['UPLOAD_FOLDER'], f'temp/{md5}')
    if not os.path.exists(chunk_dir_path):
        os.makedirs(chunk_dir_path)
    chunk_file_path = os.path.join(chunk_dir_path, f'part_{cur}')
    if not os.path.exists(chunk_file_path):
        chunk.save(chunk_file_path)

    if cur == (total - 1):
        # 合并分片文件
        with open(filepath, 'wb') as final_file:
            for findex in range(total):
                chunk_path = os.path.join(chunk_dir_path, f'part_{findex}')
                with open(chunk_path, 'rb') as chunk_file:
                    final_file.write(chunk_file.read())
                os.remove(chunk_path)
            try:
                os.rmdir(chunk_dir_path)
            except OSError as e:
                logger.info(f'delete dir err, dir = {chunk_dir_path}')
        
        video_wrapper.inser_video(file_name=filename, file_path=filepath, md5=md5)
        results = video_wrapper.find_video_by_md5(md5=md5)
        logger.info(dict(results[0]))
        # 将文件信息保存到数据库
        return ApiResponse(200, '文件上传成功', dict(results[0])).to_json()
    return ApiResponse(200, '分片文件保存成功', filepath).to_json()



# 获取视频流
@app.route('/video/stream/<string:filename>')
def video_stream(filename):
    video_wrapper = VideoWrapper(app.config['DB_FILE_PATH'] )
    results = video_wrapper.find_video_by_filename(filename)
    if not results:
        return ApiResponse(-1, '视频记录不存在', None).to_json()
    video_row = dict(results[0])
    file_path = os.path.join(video_row['file_path'])
    if not os.path.exists(file_path):
        return ApiResponse(-1, '视频文件不存在', None).to_json()

    range_hander = request.headers.get('Range', None)
    
    if not range_hander:
        
        def generate():
            with open(file_path, 'rb') as video_file:
                while True:
                    chunk = video_file.read(1024*1024)
                    if not chunk:
                        break
                    yield chunk

        return Response(stream_with_context(generate()), mimetype='video/mp4')

    else:
        logger.info(f'range_hander = {range_hander}')
        size = os.path.getsize(file_path)
        byte1, byte2 = 0, None
        m = re.search('(\d+)-(\d*)', range_hander)
        g = m.groups()

        byte1, byte2 = int(g[0]), g[1]
        byte2 = int(byte2) if byte2 else size - 1

        length = byte2 - byte1 + 1
        data = None
        with open(file_path, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)

        rv = Response(data, 206, mimetype='video/mp4', content_type='video/mp4', direct_passthrough=True)
        rv.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{size}')
        rv.headers.add('Accept-Ranges', 'bytes')
        return rv



# 将指定文件转为mp4类型
@app.route('/video/parse_mp4', methods=['POST'])
def parse_mp4():
    '''
        filename: 文件名称
        rebuild: 如果为True,则不管存在都重新生成, false则存在就不重新生成
    '''
    data = request.json
    filename = data.get('filename') 
    rebuild = data.get('rebuild')
    
    video_wrapper = VideoWrapper(app.config['DB_FILE_PATH'] )
    results = video_wrapper.find_video_by_filename(filename)
    if not results or len(results) == 0:
        return ApiResponse(-1, '视频信息不存在', None).to_json()

    video_row = dict(results[0])
    # filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    filepath = video_row.get('file_path')
    if not os.path.exists(filepath):
        return ApiResponse(-1, '视频源文件不存在', None).to_json()
    
    file_name_prefix = os.path.basename(filename).split('.')[0]
    parse_file_name = file_name_prefix + '.mp4'
    parse_file_path = os.path.join(app.config['UPLOAD_FOLDER'], parse_file_name)
    logger.info(f'fllepath: {filepath}')
    mp4_results = video_wrapper.find_video_by_filename(parse_file_name)
    if mp4_results and len(mp4_results) > 0:
        return ApiResponse(200, '转换成功', dict(mp4_results[0])).to_json()

    
    try:
        def generate():
            for progress in convert_video_sys(filepath, parse_file_path):
                if progress.startswith('100.'):
                    new_md5 = md5_file(parse_file_path)
                    video_wrapper.update_video(parse_file_name, parse_file_path, new_md5, video_row.get('id'))
                    mp4_results = video_wrapper.find_video_by_md5(new_md5)
                    yield ApiResponse(200, 'WORK', { 'progress': progress, 'video': dict(mp4_results[0]) }).to_json()
                else:
                    yield ApiResponse(200, 'WORK', { 'progress': progress, 'video': None }).to_json()
        return Response(generate(), mimetype="text/event-stream")
    except err:
        return ApiResponse(-1, '视频转换失败', None).to_json()


# 查询视频音频
@app.route('/audio/videoid/<id>')
def find_audio_by_video_id(id):
    audio_wrapper = AudioWrapper(app.config['DB_FILE_PATH'])
    results = audio_wrapper.find_audio_by_video_id(id)
    if results and len(results) > 0:
        return ApiResponse(200, "SUCCESS", dict(results[0])).to_json()
    return ApiResponse(200, "EMPTY", None).to_json()


# 加载视频的音频以及已经剪辑的音频
@app.route('/audio/videoid/list')
def list_audios_by_video_id():
    pass


# 提取音频
@app.route('/video/extract_wav', methods=['POST'])
def extract_wav():
    data = request.json
    video_id = data.get('video_id') 
    rebuild = data.get('rebuild')

    # 获取视频信息，检查视频是否存在  
    video_wrapper = VideoWrapper(app.config['DB_FILE_PATH'] )
    video_results = video_wrapper.find_video_by_id(video_id)
    if not video_results or len(video_results) == 0:
        return ApiResponse(-1, '视频信息不存在', None).to_json()

    video_row = dict(video_results[0])
    video_name = video_row.get('file_name')
    # 视频路径
    video_path = video_row.get('file_path')
    if not os.path.exists(video_path):
        return ApiResponse(-1, '视频源文件不存在', None).to_json()

    # 检查音频是否存在
    audio_wrapper = AudioWrapper(app.config['DB_FILE_PATH'])
    audio_results = audio_wrapper.find_audio_by_video_id(video_id)
    if len(audio_results) > 0:
        return ApiResponse(200, '音频已经存在', dict(audio_results[0])).to_json()

   
    # 文件名称
    audio_prefix = os.path.basename(video_name).split('.')[0]
    # 输出文件名称
    audio_name = audio_prefix + '.wav'
    # 输出文件路径
    audio_path = os.path.join(app.config['UPLOAD_FOLDER'], audio_name)
    logger.info(f'fllepath: {video_path}')
    
    if os.path.exists(audio_path):
        if rebuild:
            os.remove(audio_path)
        else:
            return ApiResponse(200, '音频已经存在了', audio_name).to_json()
    
    try:
        def generate():
            for progress in extract_audio(video_path, audio_path):
                logger.info(f'progress: {progress}')
                if progress == 'finish':
                    audio_md5 = md5_file(audio_path)
                    audio_wrapper.inser_audio(video_id, audio_name, audio_path, audio_md5)
                    audio_results = audio_wrapper.find_audio_by_md5(audio_md5)
                    yield ApiResponse(200, 'WORK', { 'progress': '100.0', 'audio': dict(audio_results[0]) }).to_json()
                else:
                    yield ApiResponse(200, 'WORK', { 'progress': progress, 'audio': None }).to_json()
        return Response(generate(), mimetype="text/event-stream")
        
    except err:
        return ApiResponse(-1, '音频提取失败', None).to_json()



# 截取音频
@app.route('/audio/cut_wav', methods=['POST'])
def cut_wav():
    data = request.json
    audio_id = data.get('audio_id') 
    rebuild = data.get('rebuild')
    start_ms = int(data.get('start_ms'))
    end_ms = int(data.get('end_ms'))
    
    audio_wrapper = AudioWrapper(app.config['DB_FILE_PATH'])
    audio_results = audio_wrapper.find_audio_by_id(audio_id)

    if not audio_results or len(audio_results) <= 0:
        return ApiResponse(-1, '音频源文件不存在', None).to_json()
    audio_row = dict(audio_results[0])
    audio_id = audio_row.get('id')
    audio_name = audio_row.get('file_name')
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], audio_name)
    if not os.path.exists(filepath):
        return ApiResponse(-1, '音频源文件不存在', None).to_json()

    logger.info(f'fllepath: {filepath}')

    result = extract_wav_audio(filepath, '', start_ms, end_ms)
    cut_path = result.get('path')
    cut_name = result.get('name')
    audio_cut_wrapper = AudioCutWrapper(app.config['DB_FILE_PATH'])
    file_md5 = md5_file(cut_path)
    audio_cut_wrapper.inser_audio_cut(audio_id, cut_name, cut_path, file_md5)
    cut_results = audio_cut_wrapper.find_audio_cut_by_md5(file_md5)
    return ApiResponse(200, '音频提取成功', dict(cut_results[0])).to_json()


# 查询剪辑音频
@app.route('/audio/cut/main/<audio_main_id>')
def list_audio_cut_by_ami(audio_main_id):
    audio_cut_wrapper = AudioCutWrapper(app.config['DB_FILE_PATH'])
    results = audio_cut_wrapper.list_audio_cut_by_ami(audio_main_id)
    results = [dict(item) for item in results]
    return ApiResponse(200, "SUCCESS", results).to_json()


# 查询剪辑音频
@app.route('/audio/cut/list')
def list_audio_cut():
    audio_cut_wrapper = AudioCutWrapper(app.config['DB_FILE_PATH'])
    results = audio_cut_wrapper.list_audio_cut()
    results = [dict(item) for item in results]
    return ApiResponse(200, "SUCCESS", results).to_json()


# 删除剪辑音频
@app.route('/audio/cut/del/<id>')
def del_audio_cut(id):
    logger.info(f'id = {id}')
    audio_cut_wrapper = AudioCutWrapper(app.config['DB_FILE_PATH'])
    results = audio_cut_wrapper.find_audio_cut_by_id(id)
    if len(results) == 0:
        return ApiResponse(-1, "视频不存在", None).to_json()
    audio_cut = dict(results[0])
    logger.info(f'audio_cut = {audio_cut}')
    file_path = audio_cut.get('file_path')
    if os.path.exists(file_path):
        os.remove(file_path)
    audio_cut_wrapper.del_by_id(id)
    return ApiResponse(200, "SUCCESS", None).to_json()



# 音频转文本
@app.route('/audio/extract/text', methods=['POST'])
def audioExtractText():
    audio_id = request.json.get('audio_id')
    model_size = request.json.get('model_size')
    lan = request.json.get('lan')

    audio_cut_wrapper = AudioCutWrapper(app.config['DB_FILE_PATH'])
    audio_results = audio_cut_wrapper.find_audio_cut_by_id(audio_id)

    if not audio_results or len(audio_results) <= 0:
        return ApiResponse(-1, '音频记录不存在', None).to_json()

    if not model_size:
        model_size = 'medium'

    audio_row = dict(audio_results[0])
    logger.info(f'audio_row = {audio_row}')
    id = audio_row.get('id')
    file_path = audio_row.get('file_path')

    if not os.path.exists(file_path):
        return ApiResponse(-1, '音频文件不存在', None).to_json()

    if not lan:
        lan = 'en'
    elif lan == 'zh':
        initial_prompt = '以下是普通话句子'
        
    # 检查音频文件大小，最好不要太大
    
    # 加载模型
    model = whisper.load_model(model_size)
    result = model.transcribe(file_path, language=lan, initial_prompt=initial_prompt)
    logger.info(f"reslut.text = {result['text']}")

    if not audio_row['trans_text']:
        # 更新下音频文本
        audio_cut_wrapper.update_audio_cut_text(id, result['text'], result['language'])

    audio_text_segments_wrapper = AudioTextSegmentsWrapper(app.config['DB_FILE_PATH'])
    ats_results = audio_text_segments_wrapper.list_by_audio_id(id)
    if not ats_results or len(ats_results) == 0:
        for item in result['segments']:
            audio_text_segments_wrapper.inser_audio_text_segments(audio_id, item)
    audio_results = audio_cut_wrapper.find_audio_cut_by_id(audio_id)
    return ApiResponse(200, 'SUCCESS', dict(audio_results[0])).to_json()



@app.route('/audio/stream/<path:filepath>')
def audio_stream(filepath):
    def generate():
        with open(filepath, "rb") as fwave:
            data = fwave.read(1024)
            while data:
                yield data
                data = fwave.read(1024)
    return Response(generate(), mimetype="audio/x-wav")



@app.route('/audio/text/segments/<audio_id>')
def list_audio_text_segments(audio_id):
    audio_text_segments_wrapper = AudioTextSegmentsWrapper(app.config['DB_FILE_PATH'])
    results = audio_text_segments_wrapper.list_by_audio_id(audio_id=audio_id)
    return ApiResponse(200, 'SUCCESS', [dict(item) for item in results]).to_json()
    

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument("-frp", type=bool, default=False,help="open frp")
    parser.add_argument("-frp-config-path", type=str, default='',help="frp config paht")
    parser.add_argument('-dbinit', type=bool, default=False, help="clear db, start new project")
    parser.add_argument('-model', type=str, default='large', help="load whisper model")
    parser.add_argument('--processes', type=int, default=0, help="cpu_processes")
    args, _ = parser.parse_known_args()

    if args.initdb:
        logger.info(f'init db: {True}')
        init_db()
    if args.frp:
        frp_config = args.get('frp-config-path', '')
        start_frp(frp_config)
    if args.model:
        init_model(args.model)
    app.run(host='0.0.0.0', port=9081)
    
    
    