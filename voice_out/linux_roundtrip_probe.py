"""Bounded server-only roundtrip; no token refresh, shell or file executor."""
import asyncio,json,logging,pathlib,sys,threading,time,uuid
from musegadget import muse_api
from musegadget.link_client import DeviceDescription,LinkSession

logging.basicConfig(level=logging.WARNING)
spec={'voiceshell.reply':{'description':'Return text to the current VoiceShell test. No shell or file access.',
 'required':{'correlation':{'type':'string','description':'Exact ID in the request'},'text':{'type':'string','description':'Answer, at most 1024 UTF-8 bytes'}},'optional':{}}}

async def main():
    pairing=json.loads(pathlib.Path(sys.argv[1]).read_text())
    node='homelink-'+pairing['mac'].replace(':','')[-6:]
    for turn in (1,2):
        vms,status=await asyncio.to_thread(muse_api.fetch_vms_with_status,pairing['access_token'],muse_api.api_root(pairing.get('api_url_v2','')))
        print(json.dumps({'phase':'vm_lookup','status':status,'available':len(vms)}),flush=True)
        if status!=200 or not vms:raise RuntimeError('VM_LOOKUP_FAILED')
        correlation=str(uuid.uuid4());result={};lock=threading.Lock()
        def receive(command,params,timeout_ms=None):
            if command!='voiceshell.reply' or not isinstance(params,dict):return {'ok':False,'error':'unsupported'}
            text=params.get('text')
            if params.get('correlation')!=correlation or not isinstance(text,str) or not text or len(text.encode())>1024:return {'ok':False,'error':'invalid_reply'}
            with lock:
                if result and result['text']!=text:return {'ok':False,'error':'conflicting_reply'}
                result['text']=text
            return {'ok':True,'payload':{'received':True}}
        vm=vms[0];stop=asyncio.Event()
        session=LinkSession(noise_host=pairing.get('noise_host') or 'hatch.metaaivm.com',vm_id=vm['vm_id'] or vm['vm_name'],vm_auth_token=vm['vm_auth_token'],device=DeviceDescription(node,'VoiceShell Linux Bridge Test','0.1.0',spec),run_command=receive)
        task=asyncio.create_task(session.run(stop));start=time.monotonic()
        try:
            while session.registered_at is None:
                if task.done():raise RuntimeError('SESSION_ENDED_BEFORE_REGISTER')
                if time.monotonic()-start>40:raise TimeoutError('REGISTER_TIMEOUT')
                await asyncio.sleep(.2)
            print(json.dumps({'phase':'linux_registered','turn':turn}),flush=True)
            message=f'VoiceShell Linux服务器独立测试第{turn}轮。ESP32已停止运行，本消息由Linux直接发出。请调用本设备 voiceshell.reply 工具，correlation="{correlation}"，text="第{turn}轮：Linux直连回传成功"。不要调用其他工具。'
            ack=await session.send_chat(message)
            print(json.dumps({'phase':'sent','turn':turn,'http':ack['status'],'accepted':ack['ok']}),flush=True)
            if not ack['ok']:raise RuntimeError('SEND_REJECTED')
            deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                with lock:text=result.get('text')
                if text:
                    print(json.dumps({'phase':'reply','turn':turn,'text':text,'seconds':round(time.monotonic()-start,1)},ensure_ascii=True),flush=True)
                    await asyncio.sleep(1)
                    break
                if task.done():raise RuntimeError('SESSION_ENDED')
                await asyncio.sleep(.3)
            else:raise TimeoutError('REPLY_TIMEOUT')
        finally:
            stop.set()
            try:await asyncio.wait_for(task,10)
            except asyncio.TimeoutError:task.cancel()
    print('SERVER_ONLY_TWO_SESSIONS_PASSED',flush=True)

try:asyncio.run(main())
except Exception as exc:
    print('TEST_FAILED_TYPE='+type(exc).__name__,flush=True)
    sys.exit(1)
