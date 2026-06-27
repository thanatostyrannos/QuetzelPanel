# CONFIG — deployment profile

```yaml
project: QuetzelPanel
domain: quetzel.gg
namespace: quetzel
profile: local        # local | prod
```

## profile = local (this machine)
Target: Rancher Desktop on Windows 11 + WSL2, Kubernetes = k3s.

Rely on k3s bundled components — DO NOT replace:
- **ServiceLB (Klipper)** — `type: LoadBalancer` gets the node IP as EXTERNAL-IP, zero config.
- **Traefik** ingress controller (80/443).
- **local-path** StorageClass (default) for PVCs.
- CoreDNS, metrics-server.

Explicitly NOT installed locally (would conflict / pointless on single node):
- MetalLB (conflicts with ServiceLB), Longhorn (multi-node HA pointless).

## profile = prod (non-k3s bare metal) — stubs only, wired but disabled locally
`install.sh` branch installs: MetalLB (+ IPAddressPool autoAssign:false), Longhorn,
ingress-nginx, cert-manager, kube-prometheus-stack. Left as a documented branch; not exercised locally.
