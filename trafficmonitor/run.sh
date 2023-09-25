#!/usr/bin/env bash

pods=$(kubectl get pod -n social-network | awk '{print $1}' | sed '1d')
veths=""
declare -A myMap
for pod in $pods; do
    echo $pod
    iflink=$(kubectl exec -n social-network $pod -- cat /sys/class/net/eth0/iflink)
    veth=$(ssh skv-node3 ip link | grep $iflink | awk '{print $2}')
    veth=${veth:0:(-5)}
    myMap[$veth]=$pod
    veths="$veths $veth"
    sleep 0.5
done

string=""
for veth in $veths; do
    echo $veth
    string="$string;sudo iftop -i $veth -t -N -n -s 500 -L 50 | grep -A 1 -E '^ *[0-9]' > ~/exper/zxz/iftop/${myMap[$veth]}-$veth.log &"
    # ssh skv-node3 "sudo iftop -i $veth -t -N -n -s 60 -L 50 | grep -A 1 -E '^ *[0-9]' > ~/exper/zxz/iftop/${myMap[$veth]}-$veth.log" &
done

ssh skv-node3 $string