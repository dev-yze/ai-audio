import hashlib


# 生成字符串哈希
def md5_str(data):
    # 创建一个MD5哈希对象
    md5_hash = hashlib.md5()
    md5_hash.update(data)
    return md5_hash.hexdigest()



# 获取文件md5
def md5_file(file_path):
    md5_hash = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


if __name__ == '__main__':
    print(md5_file('./upload/西游记1986_09.wav'))