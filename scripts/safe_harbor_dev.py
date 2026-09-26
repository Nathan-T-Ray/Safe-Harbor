#!/usr/bin/env python3
"""Start the Safe Harbor API and browser UI against MongoDB Atlas (MONGODB_URI).

MONGODB_URI is required. --local-mongo is an explicit offline fallback that starts or reuses a
dedicated local replica set on 127.0.0.1:27021; it is never selected implicitly.
"""
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT)]

LOCAL_FALLBACK_URI = 'mongodb://127.0.0.1:27021/?replicaSet=safe-harbor-dev'


def start_local_replica_set(children):
    from pymongo import MongoClient
    direct = MongoClient('mongodb://127.0.0.1:27021/?directConnection=true', serverSelectionTimeoutMS=500)
    try:
        direct.admin.command('ping')
    except Exception:
        dbpath = ROOT / 'data/safe_harbor/mongo'; dbpath.mkdir(parents=True, exist_ok=True)
        logs = ROOT / 'artifacts/private'; logs.mkdir(parents=True, exist_ok=True)
        children.append(subprocess.Popen(['mongod', '--dbpath', str(dbpath), '--port', '27021', '--bind_ip', '127.0.0.1', '--replSet', 'safe-harbor-dev', '--logpath', str(logs / 'mongodb-safe-harbor.log'), '--logappend'], cwd=ROOT, start_new_session=True))
        for _ in range(40):
            try:
                direct.admin.command('ping'); break
            except Exception:
                time.sleep(.25)
        else:
            raise RuntimeError('Dedicated MongoDB process did not become reachable')
    try:
        direct.admin.command('replSetGetStatus')
    except Exception as error:
        if getattr(error, 'code', None) != 94:
            raise
        direct.admin.command('replSetInitiate', {'_id': 'safe-harbor-dev', 'members': [{'_id': 0, 'host': '127.0.0.1:27021'}]})
    direct.close()


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    from safe_harbor.mongo import MongoConfigurationError, database_name, describe_target, make_client, mongo_uri, redact
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--local-mongo', action='store_true', help='OFFLINE FALLBACK ONLY: ignore MONGODB_URI and use a dedicated local replica set on 127.0.0.1:27021 (started if needed). Not Atlas.')
    parser.add_argument('--api-port', type=int, default=8010)
    parser.add_argument('--ui-port', type=int, default=5174)
    args = parser.parse_args()
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(ROOT / 'backend'), str(ROOT)]), 'MONGODB_DATABASE': database_name()}
    children = []
    try:
        if args.local_mongo:
            print('MongoDB: OFFLINE FALLBACK (--local-mongo) -- local replica set on 127.0.0.1:27021, NOT Atlas; MONGODB_URI is ignored for this session.', flush=True)
            start_local_replica_set(children)
            env['MONGODB_URI'] = LOCAL_FALLBACK_URI
        else:
            try:
                env['MONGODB_URI'] = mongo_uri()
            except MongoConfigurationError as error:
                sys.exit(f'Safe Harbor cannot start: {error} (For offline work only, pass --local-mongo explicitly.)')
        uri = env['MONGODB_URI']
        target = describe_target(uri)
        print(f"MongoDB target: {redact(uri)} (kind={target['kind']}, atlas={'yes' if target['kind'] == 'atlas' else 'NO'}, database={env['MONGODB_DATABASE']})", flush=True)
        if target['kind'] != 'atlas' and not args.local_mongo:
            print('WARNING: MONGODB_URI does not point at MongoDB Atlas (*.mongodb.net).', flush=True)
        client = make_client(uri)
        hello = client.admin.command('hello')
        if not hello.get('setName') and hello.get('msg') != 'isdbgrid':
            raise RuntimeError('MongoDB must support transactions: use Atlas (or the explicit --local-mongo offline fallback)')
        client.close()
        api = [sys.executable, '-m', 'uvicorn', 'safe_harbor.api:app', '--host', '127.0.0.1', '--port', str(args.api_port)]
        children.append(subprocess.Popen(api, cwd=ROOT, env=env, start_new_session=True))
        ui_env = {**env, 'API_TARGET': f'http://127.0.0.1:{args.api_port}'}
        children.append(subprocess.Popen(['npm', 'run', 'dev', '--', '--port', str(args.ui_port), '--strictPort'], cwd=ROOT / 'frontend', env=ui_env, start_new_session=True))
        print(f'Safe Harbor UI: http://127.0.0.1:{args.ui_port}', flush=True)
        print(f'Safe Harbor API: http://127.0.0.1:{args.api_port}/docs', flush=True)
        print('Mode: real-model provider configured' if env.get('OPENROUTER_API_KEY') and env.get('MODEL_ID') else 'Mode: deterministic operational available; real model is not configured', flush=True)
        while all(process.poll() is None for process in children):
            time.sleep(.5)
        failed = next((process.returncode for process in children if process.returncode), None)
        if failed:
            raise RuntimeError(f'A Safe Harbor service exited with status {failed}; inspect the service output above')
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(children):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in children:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    main()
