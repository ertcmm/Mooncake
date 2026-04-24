#!/bin/bash
export LD_LIBRARY_PATH=/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu:/root/Mooncake/test_libs:/usr/local/lib:/root/anaconda3/lib/python3.11/site-packages/mooncake
echo "Starting Master..."
/usr/local/bin/mooncake_master --enable_http_metadata_server=1 --enable-offload true --root_fs_dir=/mnt/mooncake_ssd --global_file_segment_size=10737418240 --quota_bytes=10737418240 > /root/Mooncake/master.log 2>&1 &
MASTER_PID=$!
sleep 5
export MOONCAKE_OFFLOAD_FILE_STORAGE_PATH=/mnt/mooncake_ssd_local
export MOONCAKE_OFFLOAD_STORAGE_BACKEND_DESCRIPTOR=bucket_storage_backend
echo "Starting Client..."
/usr/local/bin/mooncake_client --master_server_address=127.0.0.1:50051 --host=real_client --protocol="tcp" --device_names=lo --port=50052 --global_segment_size="5 GB" --enable_offload=true --metadata_server="P2PHANDSHAKE" > /root/Mooncake/client.log 2>&1 &
CLIENT_PID=$!
echo "Master PID: $MASTER_PID, Client PID: $CLIENT_PID"
sleep 5
ps -p $MASTER_PID $CLIENT_PID
