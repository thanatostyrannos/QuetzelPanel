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
