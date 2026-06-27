{{/* Common labels applied to every object. */}}
{{- define "quetzel.labels" -}}
app.kubernetes.io/part-of: quetzelpanel
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end -}}

{{/* Per-component selector labels. Call with (dict "ctx" . "component" "backend"). */}}
{{- define "quetzel.selectorLabels" -}}
app.kubernetes.io/name: quetzel-{{ .component }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Namespace the operator watches (defaults to the release namespace). */}}
{{- define "quetzel.watchNamespace" -}}
{{- default .Release.Namespace .Values.operator.watchNamespace -}}
{{- end -}}

{{/*
Resolve a component image. Call with (dict "ctx" . "component" "backend").
If .Values.<component>.image is set (local dev / overrides) it wins; otherwise
default to the published GHCR image at the chart's appVersion — so Chart.yaml
appVersion is the single source of truth for released image tags.
*/}}
{{- define "quetzel.image" -}}
{{- $ctx := .ctx -}}
{{- $comp := .component -}}
{{- $explicit := index $ctx.Values $comp "image" -}}
{{- if $explicit -}}
{{- $explicit -}}
{{- else -}}
{{- printf "%s/quetzel-%s:%s" $ctx.Values.image.registry $comp $ctx.Chart.AppVersion -}}
{{- end -}}
{{- end -}}
