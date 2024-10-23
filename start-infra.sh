#!/bin/bash

kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.1/cert-manager.yaml

kubectl apply -f ./deployment/namespace/apicurio-api-controller.yaml

kubectl apply -f ./deployment/apicurio-registry/postgres.yaml
kubectl apply -f ./deployment/apicurio-registry/registry-sql.yaml
kubectl apply -f ./deployment/apicurio-studio/apicurio-api-controller.yaml
kubectl apply -f ./deployment/apicurio-studio/apicurio-api-controller.yaml
kubectl apply -f ./deployment/namespace/apicurio-api-controller.yaml

kubectl create -f https://operatorhub.io/install/kuadrant-operator.yaml



minikube tunnel