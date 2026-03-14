import asyncio

from backend.core.sse_manager import SSEManager


def test_send_events_include_expected_payload_fields():
    async def scenario():
        manager = SSEManager()

        await manager.send_progress(
            task_id="task-1",
            completed_count=2,
            total_nodes=7,
            current_node="extract_tender_params",
            current_node_display="提取原始采购需求",
        )
        await manager.send_llm_output(
            task_id="task-1",
            content="你好啊",
            node="generate_polished_text",
            model="deepseek",
            is_complete=True,
        )
        await manager.send_done(
            task_id="task-1",
            output_file="D:/UploadFiles/output.docx",
            processing_time=12.5,
        )
        await manager.send_error(task_id="task-2", error="boom", is_fatal=False)

        progress_event = manager._events["task-1"][0]
        llm_event = manager._events["task-1"][1]
        done_event = manager._events["task-1"][2]
        error_event = manager._events["task-2"][0]

        assert progress_event.data["task_id"] == "task-1"
        assert "timestamp" in progress_event.data

        assert llm_event.data["task_id"] == "task-1"
        assert llm_event.data["content_mode"] == "snapshot"
        assert llm_event.data["is_complete"] is True
        assert "timestamp" in llm_event.data

        assert done_event.data["task_id"] == "task-1"
        assert done_event.data["output_file"] == "D:/UploadFiles/output.docx"
        assert "timestamp" in done_event.data

        assert error_event.data["task_id"] == "task-2"
        assert error_event.data["is_fatal"] is False
        assert "timestamp" in error_event.data

    asyncio.run(scenario())


def test_event_stream_emits_real_heartbeat_event():
    async def scenario():
        manager = SSEManager(heartbeat_interval=0.01)
        stream = manager.event_stream("task-1", "client-1")

        connected = await anext(stream)
        heartbeat = await anext(stream)
        await stream.aclose()

        assert "event: log" in connected
        assert "event: heartbeat" in heartbeat
        assert '"task_id": "task-1"' in heartbeat

    asyncio.run(scenario())


def test_event_stream_replays_history_and_stops_after_done():
    async def scenario():
        manager = SSEManager()
        await manager.send_log(task_id="task-1", message="step-1")
        await manager.send_done(task_id="task-1", output_file="D:/UploadFiles/output.docx")

        stream = manager.event_stream("task-1", "client-1", last_event_id=0)
        events = []
        async for item in stream:
            events.append(item)

        assert len(events) == 3
        assert "event: log" in events[1]
        assert "event: done" in events[2]

    asyncio.run(scenario())
