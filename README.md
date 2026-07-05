# ClipMerge
> 无损合并同格式视频片段

## 功能
- 使用 ffmpeg concat demuxer 流拷贝模式，无损无转码合并
- 自动检测视频格式一致性，避免格式不匹配导致失败
- 支持拖拽排序（上移 / 下移调整合并顺序）
- 图形化界面，操作直观

## 使用方法
```bash
python clip_merge.py
```
启动 GUI 后添加待合并视频，调整顺序，点击「开始合并」即可。需安装 ffmpeg。
