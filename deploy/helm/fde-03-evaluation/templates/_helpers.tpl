{{- define "fde.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "fde.fullname" -}}
{{- if contains .Chart.Name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "fde.labels" -}}
app.kubernetes.io/name: {{ include "fde.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: fde-series
{{- end -}}

{{- define "fde.selectorLabels" -}}
app.kubernetes.io/name: {{ include "fde.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
