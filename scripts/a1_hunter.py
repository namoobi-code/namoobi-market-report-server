#!/usr/bin/env python3
# a1_hunter.py — A1(2 OCPU/12GB) 무료 인스턴스 자동 재시도 (2026-08-14)
#   도쿄 리전 'Out of host capacity' 대응: 크론 10분 간격으로 생성 시도.
#   성공 → 크론 자기해제 + Public IP 메일 통보. 콘솔 수동 시도와 동일 설정.
import json, os, subprocess, sys, datetime as dt
import oci
FLAG='/home/ubuntu/.oci/a1_done.flag'
if os.path.exists(FLAG): sys.exit(0)
c=oci.config.from_file()
ids=json.load(open('/home/ubuntu/.oci/launch_ids.json'))
net=oci.core.VirtualNetworkClient(c, timeout=30)
# public 서브넷 강제 선택 (10.0.0.0/24)
vcns=oci.core.VirtualNetworkClient(c).list_vcns(c['tenancy']).data
subnet=[s for s in oci.core.VirtualNetworkClient(c).list_subnets(c['tenancy'], vcn_id=vcns[0].id).data if s.cidr_block=='10.0.0.0/24'][0]
cmp=oci.core.ComputeClient(c, timeout=60)
ssh_pub='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILzaw7Fo3z0gOsQg0BbTe5xzX+UfQbhLZYJzN1QpFX1Y namoobi-deploy'
def mkdetail(ocpus, mem):
    return oci.core.models.LaunchInstanceDetails(
        availability_domain=ids['ad'], compartment_id=ids['compartment'],
        display_name='namoobi-a1', shape='VM.Standard.A1.Flex',
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=ocpus, memory_in_gbs=mem),
        source_details=oci.core.models.InstanceSourceViaImageDetails(image_id=ids['image'], boot_volume_size_in_gbs=100),
        create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=subnet.id, assign_public_ip=True),
        metadata={'ssh_authorized_keys': ssh_pub})
now=dt.datetime.now().strftime('%m-%d %H:%M')
# (2026-08-15) 폴백 추가 — 2/12 가 28시간·167회 전부 용량 없음이라, 작은 조각(1/6)도 함께 노린다.
#   1/6 이라도 현 서버(1코어/954MB) 대비 메모리 6배. 용량 풀리면 나중에 2/12 로 재생성 가능.
def try_launch(ocpus, mem):
    try:
        return cmp.launch_instance(mkdetail(ocpus, mem)), None
    except oci.exceptions.ServiceError as e:
        return None, e
r=None; used=None; last_err=None
# (2026-08-16) 레이트리밋 완화 — 이틀간 180회+ 연타로 LaunchInstance 가 429 고착.
#   회차당 호출을 2회→1회로 줄이고 시간대별로 사이즈를 번갈아 시도한다(짝수시 2/12, 홀수시 1/6).
#   크론도 30분→60분. 실제 요청량은 종전의 1/4.
SIZES = ((2,12),) if dt.datetime.now().hour % 2 == 0 else ((1,6),)
for oc, mem in SIZES:
    resp, err = try_launch(oc, mem)
    if resp is not None:
        r=resp; used=f'{oc} OCPU/{mem}GB'; break
    last_err=err
    retryable = 'capacity' in str(err.message).lower() or err.status in (429, 500)  # 429=레이트리밋(167회 연타 여파) — 대기하면 풀린다
    if not retryable:
        print(now,'오류:', err.status, str(err.message)[:100]); raise SystemExit
    import time as _t; _t.sleep(8)   # 2/12 → 1/6 사이 간격(연속 호출 429 방지)
try:
    if r is None:
        print(now,f'용량/한도 대기({SIZES[0][0]}/{SIZES[0][1]}, 마지막={last_err.status}) — 다음 시도'); raise SystemExit
    iid=r.data.id
    print(now,f'생성 성공({used})! instance', iid[-12:])
    # RUNNING 대기 후 공인 IP 조회
    oci.wait_until(cmp, cmp.get_instance(iid), 'lifecycle_state', 'RUNNING', max_wait_seconds=600)
    vnics=cmp.list_vnic_attachments(ids['compartment'], instance_id=iid).data
    ip=oci.core.VirtualNetworkClient(c).get_vnic(vnics[0].vnic_id).data.public_ip
    open(FLAG,'w').write(json.dumps({'instance':iid,'public_ip':ip,'at':now}))
    body=f'A1 인스턴스 생성 성공! ({used})\n\nPublic IP: {ip}\n인스턴스: {iid}\n시각: {now}\n\nCowork 세션에서 이 IP로 이전 작업을 진행하세요.'
    payload=json.dumps({'to':'namoobi@gmail.com','bcc':[],'subject':f'[namoobi] A1 서버 생성 성공 — {ip}','body':body,'attach':[]})
    subprocess.run(['python3','/home/ubuntu/namoobi/scripts/send_report_mail.py'],input=payload.encode(),timeout=60)
    print('메일 발송 · 헌터 종료(flag)')
except oci.exceptions.ServiceError as e:
    if 'capacity' in str(e.message).lower() or e.status==500:
        print(now,'용량 없음 — 다음 시도 대기')
    else:
        print(now,'오류:', e.status, str(e.message)[:100])
