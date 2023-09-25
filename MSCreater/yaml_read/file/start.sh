#!/usr/bin/env bash

media_ip=$(kubectl -n media-microsvc1 get svc nginx-web-server | awk '{print $3}' | sed -n '2p')

pushd /home/k8s/exper/zxz/DeathStarBench/mediaMicroservice
python3 scripts/write_movie_info.py --server_address http://"$media_ip":8080
popd

for k in {1..1000} ; do
# shellcheck disable=SC2027
curl -d "first_name=first_name_""$k""&last_name=last_name_""$k""&username=username_""$k""&password=password_""$k" \
    http://"$media_ip":8080/wrk2-api/user/register
done

/home/k8s/exper/zxz/DeathStarBench/mediaMicroservice/wrk2/wrk -t 2 -c 20 -d 50s -R 25 --latency -s /home/k8s/exper/zxz/DeathStarBench/mediaMicroservice/wrk2/scripts/media-microservices/compose-review.lua http://"$media_ip":8080 > ./media_test.log
