from operation_session import operation_path
from product_integrity import pinned, state_path
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
STOCK = CASE.parent / 'receiver_stock'
USER = CASE.parent / 'receiver_custom'
STATE = operation_path('workflow/patch')
sys.path.insert(0, str(STOCK))
import orchestrator as frozen
sha, read, require = (frozen.sha, frozen.read, frozen.require)
from local_json import atomic
LOADED_SHA = sha(__file__)

def release_check():
    from product_integrity import verify_release
    return verify_release()

def reader_integrity(job, *, unused=True):
    sys.path.insert(0, str(frozen.OLD_TOOL))
    from provider import Provider
    legacy = Provider().load_legacy()
    job = Path(job)
    meta = legacy.reader_job.validate(job)
    require(not unused or not (job / 'claim.json').exists(), '读取任务已使用，禁止重复上传')
    require(meta['bytes'] == 25100288 and meta['count'] == 766 and (meta['chunk'] == 32768) and (meta['target'] == '/dev/cnflasha1') and (meta['device_id'] == '252:129') and (meta['block_writes'] is False) and (meta['automatic_retry'] is False), '读取范围发生变化')
    return meta

class Backend(frozen.WorkspaceBackend):

    def __init__(self, lineage='auto'):
        super().__init__()
        require(lineage in ('stock', 'user', 'auto'), '未知更新器类型')
        self.lineage = lineage
        self.case = STOCK if lineage == 'stock' else USER

    def check(self):
        release_check()
        from user_provider import Provider
        self.provider = Provider()
        result = self.provider.check()
        self.legacy = self.provider.load_legacy()
        result.update(validation_mode='integrity_only', per_operation_simulation=False, lineage=self.lineage)
        return result

    def runner_sha(self):
        require(sha(__file__) == LOADED_SHA, '控制器已改变')
        return LOADED_SHA

    def prepare_reader(self, folder, role='before'):
        job = Path(self.legacy.reader_job.prepare())
        meta = reader_integrity(job)
        receipt = dict(schema='m4-reader-integrity/1', nonce=meta['nonce'], job_sha256=sha(job / 'job.json'), sources=meta['sources'], worker_sha256=meta['worker']['sha256'], bootstrap_sha256=meta['bootstrap']['sha256'], validation_mode='integrity_only', simulation_executed=False)
        atomic(job / 'integrity.json', receipt)
        atomic(folder / (role + '_reader_created.json'), dict(job=str(job), hardware_operations=0))
        print('读取器完整性校验通过。', flush=True)
        return dict(job=str(job), nonce=meta['nonce'], role=role, job_sha256=receipt['job_sha256'], integrity_sha256=sha(job / 'integrity.json'))

    def verify_ready(self, job, state):
        self.check()
        require(state['runner_sha256'] == self.runner_sha(), '读取控制器不匹配')
        meta = reader_integrity(job['job'])
        path = Path(job['job'])
        require(meta['nonce'] == job['nonce'] and sha(path / 'job.json') == job['job_sha256'] and (sha(path / 'integrity.json') == job['integrity_sha256']), '读取材料变化')

    def run_reader(self, session, job, folder):
        reader_integrity(job['job'])
        require(job['role'] in ('before', 'after'), '读取阶段无效')
        if job['role'] == 'before':
            for path in ('/tmp/jbusy', '/tmp/jiritsu/libJit.so'):
                session._select('/tmp/jiritsu/../..' + path)
                try:
                    session._read_selected(1)
                except Exception as error:
                    require(getattr(error, 'status', None) == 268435462, '旧任务状态未知')
                else:
                    raise ValueError('相机仍有旧任务，未上传读取器')
        output = folder / 'execution' / job['role']
        result = self.legacy.live_reader.run_protocol(session, job['job'], output)
        verifier = frozen.load_module('m4_integrity_full_read_verifier', frozen.FULL_READ_VERIFIER)
        require(sha(frozen.FULL_READ_VERIFIER) == frozen.FULL_READ_VERIFIER_SHA, '回读验证器已改变')
        hashes = verifier.verify_full_read(output, job, expected_sha=result['sha256'])
        atomic(folder / (job['role'] + '_full_read_verification.json'), dict(passed=True, evidence=hashes, nonce=job['nonce'], p1_sha256=result['sha256']))
        print(json.dumps(dict(progress_chunks=766, total_chunks=766)), flush=True)
        return (output / 'nflasha1.bin', result)

    def adapter(self):
        return frozen.load_module('m4_integrity_receiver', self.case / 'receiver.py')

    def jobs(self):
        return frozen.load_module('receiver_writer_job', self.case / 'receiver_writer_job.py')

    def prepare_write(self, source, folder, direction, saved_bundle=None):
        if self.lineage == 'auto':
            actual = Path(source).read_bytes()
            for lineage, case in (('stock', STOCK), ('user', USER)):
                adapter = frozen.load_module('m4_integrity_candidate_' + lineage, case / 'receiver.py')
                try:
                    adapter.inspect_bytes(actual)
                except ValueError:
                    continue
                self.lineage, self.case = (lineage, case)
                break
            require(self.lineage != 'auto', '当前完整更新器不属于已审查的官方或项目固件')
        adapter = self.adapter()
        digest = sha(source)
        if direction == 'apply':
            bundle = folder / 'bundle'
            adapter.prepare(source, digest, bundle)
        else:
            bundle = Path(saved_bundle).resolve()
        manifest, original, candidate = adapter.load_bundle(bundle)
        actual = Path(source).read_bytes()
        require(actual in (original, candidate), '当前完整分区与保存的原件或候选不匹配')
        wanted = candidate if direction == 'apply' else original
        preparation = dict(direction=direction, lineage=self.lineage, bundle=str(bundle), bundle_sha256=sha(bundle / 'bundle.json'), source_sha256=digest, target_sha256=hashlib.sha256(wanted).hexdigest(), no_change=actual == wanted, final_state=adapter.inspect_bytes(wanted)[0], validation_mode='integrity_only', simulation_executed=False)
        if preparation['no_change']:
            return preparation
        jobs = self.jobs()
        root = state_path(self.case) / ('writer_userflow_' + folder.name)
        root.mkdir(parents=True, exist_ok=False)
        paths = {}
        for role in ('apply', 'restore'):
            path = root / role
            jobs.prepare(bundle, role, path)
            paths[role] = str(path)
        preparation.update(jobs=paths, writer_job=paths[direction])
        preparation['integrity_hashes'] = {str(Path(path) / 'job.json'): sha(Path(path) / 'job.json') for path in paths.values()}
        self.prove_writer(preparation)
        print('补丁和恢复材料完整性校验通过，未运行仿真或故障注入。', flush=True)
        return preparation

    def prove_writer(self, preparation):
        require(preparation['lineage'] == self.lineage and preparation['validation_mode'] == 'integrity_only' and (preparation['simulation_executed'] is False), '补丁材料类型不匹配')
        paths = preparation['jobs']
        require(set(paths) == {'apply', 'restore'} and preparation['direction'] in paths and (Path(preparation['writer_job']).resolve() == Path(paths[preparation['direction']]).resolve()), '写入方向不匹配')
        required = {str(Path(path) / 'job.json') for path in paths.values()}
        require(set(preparation['integrity_hashes']) == required and all((sha(path) == digest for path, digest in preparation['integrity_hashes'].items())), '补丁任务清单已改变')
        jobs = self.jobs()
        metas = {}
        for direction, path in paths.items():
            require(not (Path(path) / 'claim.json').exists(), '写入任务已使用')
            meta = jobs.validate(path)
            require(meta['direction'] == direction, '材料方向不匹配')
            metas[direction] = meta
        require(metas['apply']['source_sha256'] == metas['restore']['target_sha256'] and metas['apply']['target_sha256'] == metas['restore']['source_sha256'], '恢复材料不匹配')
        chosen = metas[preparation['direction']]
        require(chosen['source_sha256'] == preparation['source_sha256'] and chosen['target_sha256'] == preparation['target_sha256'], '实际写入摘要不匹配')
        return chosen

    def verify_write_ready(self, preparation, after_job, state):
        self.check()
        self.verify_ready(after_job, state)
        require(sha(Path(preparation['bundle']) / 'bundle.json') == preparation['bundle_sha256'], '备份清单已改变')
        self.prove_writer(preparation)

    def run_writer(self, session, preparation, folder):
        release_check()
        meta = self.prove_writer(preparation)
        protocol = frozen.load_module('receiver_usb_writer_user', CASE / 'receiver_usb_writer_user.py')
        output = folder / 'execution/writer'
        result = protocol.run_protocol(session, preparation['writer_job'], output)
        jobs = self.jobs()
        ready, final = (jobs.decode((output / (name + '.bin')).read_bytes(), meta) for name in ('ready', 'result'))
        require(final == result.get('native') and final['phase'] == 6 and (final['error'] == 0) and (final['flags'] == 255) and (final['rollback'] == 0) and (final['io_status'] == 0) and (final['before_sha256'] == preparation['source_sha256']) and (final['after_sha256'] == preparation['target_sha256']) and all((final[k] == ready[k] for k in ('euid', 'pid', 'ppid', 'loader_pid', 'cleanup'))) and (result.get('module_uploads') == result.get('prepare_attempts') == result.get('commit_attempts') == 1) and (result.get('readback_windows') == len(meta['windows'])), '写入结果未完整确认')
        return result

    def verify_written(self, source, after, preparation):
        adapter = self.adapter()
        _, original, candidate = adapter.load_bundle(preparation['bundle'])
        actual = Path(after).read_bytes()
        require(actual == (candidate if preparation['direction'] == 'apply' else original) and sha(source) == preparation['source_sha256'], '独立完整回读不一致')
        adapter.verify_patch_semantics(original, candidate)
        return adapter.inspect_bytes(actual)[0]
