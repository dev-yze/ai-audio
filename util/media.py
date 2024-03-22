import ffmpeg
import moviepy.editor as mpe
from tqdm import tqdm
from pydub import AudioSegment
from pydub.silence import split_on_silence
import os
import sys
import re
import subprocess

# 允许上传的类型
ALLOWED_EXTENSIONS = { 'mp3' }
# ALLOWED_EXTENSIONS = {'txt','pdf', 'png', 'jpg', 'jpeg', 'gif'}

# 检查允许的文件类型
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



def convert_to_mp4(input_file, out_file):
    ffmpeg.input(input_file).output(out_file, vcodec='libx264', acodec='aac').run(overwrite_output=True)


'''
将视频转为mp4格式
'''
def convert_video_sys(input_file, output_file):
    command = ['ffmpeg', '-i', input_file, '-vcodec', 'libx264', '-acodec', 'aac', output_file]

    ffmpeg = subprocess.Popen(command, stderr=subprocess.PIPE, universal_newlines=True)

    duration = None

    for line in iter(ffmpeg.stderr.readline, ""):
        # Extract duration
        if duration is None:
            match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2})\.\d{2}", line)
            if match:
                hours, mins, secs = map(int, match.groups())
                duration = hours * 3600 + mins * 60 + secs

        # Extract time
        else:
            match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})\.\d{2}", line)
            if match:
                hours, mins, secs = map(int, match.groups())
                time = hours * 3600 + mins * 60 + secs
                progress = (time / duration) * 100
                
                yield f"{progress}"
                # sys.stdout.write(f"\rProgress: {progress:.2f}%")
                # sys.stdout.flush()

    ffmpeg.wait()



'''
提取视频音频
'''
def extract_audio(input_file, output_file):
    command = ['ffmpeg', '-i', input_file, '-vn', '-ab', '192k', output_file]
    ffmpeg = subprocess.Popen(command, stderr=subprocess.PIPE, universal_newlines=True)

    duration = None


    for line in iter(ffmpeg.stderr.readline, ""):
        
        if duration is None:
            match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})", line)
            if match:
                hours, mins, secs, msec = map(int, match.groups())
                duration = hours * 3600 + mins * 60 + secs
                duration = duration * 1000 + msec

        # Extract time
        elif re.match(r"video:0kB audio", line):
            yield f"finish"
        else:
            match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})", line)
            if match:
                hours, mins, secs, msec = map(int, match.groups())
                time = hours * 3600 + mins * 60 + secs
                time = time * 1000 + msec
                progress = (time / duration) * 100
                # print(f"line = {progress}")
                yield f"{progress}"
                # sys.stdout.write(f"\rProgress: {progress:.2f}%")
                # sys.stdout.flush()

    ffmpeg.wait()



def mp4_to_audio(mp4_path, save_path):
    '''
		从mp4文件提取音频,可转换为wav或mp3
		mp4_path: mkv文件路径
		save_path: 保存文件路径
    '''
    video = mpe.VideoFileClip(mp4_path)
    audio = video.audio
    audio.write_audiofile(save_path)







# 提取指定时间段音频
def extract_wav_audio(audio_file_path, save_path, start_ms, end_ms):
    '''
		audio_file_path: 文件路径
		save_path: 保存路径
		start_s: 开始时间, 多少秒
  		end_s: 结束时间, 多少秒
    '''
    if not os.path.exists(audio_file_path):
        print('wav file not exists!')
        return
    file_name = os.path.basename(audio_file_path)
    file_name_prefix = file_name.split('.')[0]
    # 载入WAV文件
    audio = AudioSegment.from_wav(audio_file_path)
    if not save_path:
        save_path = audio_file_path[0:-4]
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    chunk = audio[(start_ms):(end_ms)]

    cutname = f"{file_name_prefix}_part_{start_ms}-{end_ms}.wav"
    part_save_path = os.path.join(save_path, cutname)
    if os.path.exists(part_save_path):
        os.remove(part_save_path)
    chunk.export(part_save_path, format="wav")
    return { 'path': part_save_path, 'name':  cutname}



def auto_cut_wav(audio_file_path):
    # 加载音频文件
    audio = AudioSegment.from_wav(audio_file_path)
    save_path = audio_file_path[0:-4] + '/temp-auto/'
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    # 根据停顿切割音频
    # min_silence_len 参数是停顿的最小长度（毫秒）
    # silence_thresh 参数是认为是静默的阈值（分贝）
    print('开始切割文件: ')
    chunks = split_on_silence(
        audio,
        min_silence_len=1000,
        silence_thresh=audio.dBFS-14,
        keep_silence=500
    )
    print(f'切割文件完成: {len(chunks)}')
    
    for i, chunk in enumerate(chunks):
        chunk_path = os.path.join(save_path, f'chunk_{i}.wav')
        chunk.export(chunk_path, format="wav")



if __name__ == '__main__':
    # convert_to_mp4('./upload/西游记1986_09.mkv', './upload/西游记1986_09.mp4')
    # mp4_to_audio('./upload/西游记1986_09.mp4', './upload/西游记1986_09_part.wav')
    # extract_wav_audio('./upload/西游记1986_09.wav', '', 5000, 20000)
    # print('---main---')
    # extract_audio('./upload/西游记1986_09.mp4', './upload/西游记1986_09.wav')

    auto_cut_wav('../upload/西游记1986_09.wav')
    
    