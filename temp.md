# NOTES

```shell
cd backend
uv run run_server.py
```

```shell
cd backend
uv run run_agent.py --agent-type online_teacher_agent --command-json script_generator/output/command.json
```

```shell
cd frontend
pnpm run dev
```


生成script_generator/output/command.json
```shell
cd backend
uv run script_generator/script_generator.py
```

启动弹幕监听服务器
```shell
cd backend/danmaku_retriever
python danmaku_server.py --port 8001 --room-ids 4632700
```
网络开拓者的直播间: 4632700
硅硅草的直播间: 1790373997

断点继续 - PPT
```shell
uv run run_agent.py --agent-type online_teacher_agent --command-json script_generator/output/command.json --start-at ppt:PAGE
```

断点继续 - 互动
```shell
uv run run_agent.py --agent-type online_teacher_agent --command-json script_generator/output/command.json --start-at interaction:NAME
```
