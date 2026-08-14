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
detail=oci.core.models.LaunchInstanceDetails(
    availability_domain=ids['ad'], compartment_id=ids['compartment'],
    display_name='namoobi-a1', shape='VM.Standard.A1.Flex',
    shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=2, memory_in_gbs=12),
    source_details=oci.core.models.InstanceSourceViaImageDetails(image_id=ids['image'], boot_volume_size_in_gbs=100),
    create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=subnet.id, assign_public_ip=True),
    metadata={'ssh_authorized_keys': ssh_pub})
now=dt.datetime.now().strftime('%m-%d %H:%M')
try:
    r=cmp.launch_instance(detail)
    iid=r.data.id
    print(now,'생성 성공! instance', iid[-12:])
    # RUNNING 대기 후 공인 IP 조회
    oci.wait_until(cmp, cmp.get_instance(iid), 'lifecycle_state', 'RUNNING', max_wait_seconds=600)
    vnics=cmp.list_vnic_attachments(ids['compartment'], instance_id=iid).data
    ip=oci.core.VirtualNetworkClient(c).get_vnic(vnics[0].vnic_id).data.public_ip
    open(FLAG,'w').write(json.dumps({'instance':iid,'public_ip':ip,'at':now}))
    body=f'A1 인스턴스 생성 성공!\n\nPublic IP: {ip}\n인스턴스: {iid}\n시각: {now}\n\nCowork 세션에서 이 IP로 이전 작업을 진행하세요.'
    payload=json.dumps({'to':'namoobi@gmail.com','bcc':[],'subject':f'[namoobi] A1 서버 생성 성공 — {ip}','body':body,'attach':[]})
    subprocess.run(['python3','/home/ubuntu/namoobi/scripts/send_report_mail.py'],input=payload.encode(),timeout=60)
    print('메일 발송 · 헌터 종료(flag)')
except oci.exceptions.ServiceError as e:
    if 'capacity' in str(e.message).lower() or e.status==500:
        print(now,'용량 없음 — 다음 시도 대기')
    else:
        print(now,'오류:', e.status, str(e.message)[:100])
