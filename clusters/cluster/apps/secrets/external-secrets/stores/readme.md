must create secret to allow k8s to talk to vault

```bash
kubectl create secret generic vault-token --from-literal=token=$root_token --namespace secrets
```
