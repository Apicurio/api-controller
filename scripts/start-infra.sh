#!/bin/bash

kubectl apply -f ./deployment/namespace/apicurio-api-controller.yaml

kubectl apply --server-side -f https://github.com/envoyproxy/gateway/releases/download/v1.1.2/install.yaml
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.1/cert-manager.yaml
kubectl create -f https://operatorhub.io/install/kuadrant-operator.yaml -n api-controller
kubectl create -f https://strimzi.io/install/latest?namespace=api-controller -n api-controller

kubectl apply -f ./deployment/apicurio-registry/postgres.yaml
kubectl apply -f ./deployment/apicurio-registry/registry-sql.yaml
kubectl apply -f ./deployment/apicurio-studio/apicurio-studio.yaml

kubectl apply -f ./deployment/kafka/kafka.yaml
kubectl apply -f ./deployment/kafka/kafka-connect.yaml

kubectl apply -f ./deployment/debezium/postgresql-source.yaml
