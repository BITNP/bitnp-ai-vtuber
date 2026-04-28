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
python danmaku_server.py --room-ids 1790373997 --port 8001
```