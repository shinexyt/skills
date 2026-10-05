#Requires -Version 5.1
<#
.SYNOPSIS
    为小说工作区生成单文件本地阅读器 viewer.html（没有 Python 时的等效实现）。

.DESCRIPTION
    与 build_viewer.py 产出形状完全一致的 payload，共用同一份 viewer_template.html。
    改动 payload 结构时，两个脚本必须同步修改。

.PARAMETER Dir
    小说工作区目录。

.PARAMETER Out
    输出路径，默认 <Dir>\viewer.html。

.PARAMETER Open
    生成后用默认浏览器打开。

.EXAMPLE
    powershell -File build_viewer.ps1 -Dir "D:\Repo\Novels\新小说" -Open
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Dir,

    [string]$Out,

    [switch]$Open
)

$ErrorActionPreference = 'Stop'

$Token = '@@NOVEL_DATA@@'
$SchemaVersion = 1
$TemplatePath = Join-Path $PSScriptRoot 'viewer_template.html'
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Fail([string]$Message) {
    Write-Error $Message
    exit 1
}

# ---------------------------------------------------------------------------
# 读取工作区
# ---------------------------------------------------------------------------

function Read-JsonOptional {
    param(
        [string]$Path,
        [System.Collections.ArrayList]$Notices,
        [string]$Label
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    try {
        $raw = [System.IO.File]::ReadAllText($Path, $Utf8NoBom)
        return ($raw | ConvertFrom-Json)
    }
    catch {
        [void]$Notices.Add(@{ level = 'warn'; message = "$Label 无法解析，相关视图将为空：$($_.Exception.Message)" })
        return $null
    }
}

function Get-ChapterRows {
    param(
        [string]$Folder,
        [System.Collections.ArrayList]$Notices
    )
    if (-not (Test-Path -LiteralPath $Folder -PathType Container)) {
        [void]$Notices.Add(@{ level = 'info'; message = '未找到 chapters/ 目录，尚无正文。' })
        return
    }

    $rows = New-Object System.Collections.ArrayList
    $files = Get-ChildItem -LiteralPath $Folder -File |
        Where-Object { $_.Extension -eq '.md' -or $_.Extension -eq '.markdown' } |
        Sort-Object Name

    foreach ($file in $files) {
        try {
            $text = [System.IO.File]::ReadAllText($file.FullName, $Utf8NoBom)
        }
        catch {
            [void]$Notices.Add(@{ level = 'warn'; message = "$($file.Name) 读取失败：$($_.Exception.Message)" })
            continue
        }

        $seed = $null
        $match = [regex]::Match($file.BaseName, '^(\d+)')
        if ($match.Success) { $seed = [int]$match.Groups[1].Value }

        $title = ''
        foreach ($line in ($text -replace "`r`n", "`n" -split "`n")) {
            $found = [regex]::Match($line, '^\s*#\s+(.*)$')
            if ($found.Success) { $title = $found.Groups[1].Value.Trim(); break }
        }
        if ([string]::IsNullOrWhiteSpace($title)) {
            if ($null -ne $seed) { $title = "第$seed章" } else { $title = $file.BaseName }
        }

        [void]$rows.Add([pscustomobject]@{
                seq       = $seed
                file      = $file.Name
                title     = $title
                markdown  = $text
                charCount = ([regex]::Replace($text, '\s+', '')).Length
            })
    }

    $rows |
        Sort-Object @{ Expression = { if ($null -eq $_.seq) { 1 } else { 0 } } },
                    @{ Expression = { if ($null -eq $_.seq) { 0 } else { $_.seq } } },
                    file
}

function Build-Payload {
    param([string]$Workspace)

    $notices = New-Object System.Collections.ArrayList

    $project = Read-JsonOptional -Path (Join-Path $Workspace 'project.json') -Notices $notices -Label 'project.json'
    if (-not (Test-Path -LiteralPath (Join-Path $Workspace 'project.json') -PathType Leaf)) {
        [void]$notices.Add(@{ level = 'warn'; message = '未找到 project.json，概览的设定区将为空。' })
    }

    $blueprint = Read-JsonOptional -Path (Join-Path $Workspace 'blueprint.json') -Notices $notices -Label 'blueprint.json'
    if (-not (Test-Path -LiteralPath (Join-Path $Workspace 'blueprint.json') -PathType Leaf)) {
        [void]$notices.Add(@{ level = 'info'; message = '未找到 blueprint.json，蓝图视图将为空。' })
    }

    $outline = Read-JsonOptional -Path (Join-Path $Workspace 'outline.json') -Notices $notices -Label 'outline.json'
    if (-not (Test-Path -LiteralPath (Join-Path $Workspace 'outline.json') -PathType Leaf)) {
        [void]$notices.Add(@{ level = 'info'; message = '未找到 outline.json，路线视图将为空。' })
    }

    # state.json 是备忘而非契约，缺失时不加提示——状态视图自身会说明。
    $state = Read-JsonOptional -Path (Join-Path $Workspace 'state.json') -Notices $notices -Label 'state.json'

    $chapters = @(Get-ChapterRows -Folder (Join-Path $Workspace 'chapters') -Notices $notices)

    [pscustomobject][ordered]@{
        schemaVersion = $SchemaVersion
        generatedAt   = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        workspaceName = (Split-Path -Leaf $Workspace)
        project       = $project
        blueprint     = $blueprint
        outline       = $outline
        state         = $state
        chapters      = $chapters
        notices       = @($notices)
    }
}

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

if (-not (Test-Path -LiteralPath $Dir -PathType Container)) { Fail "目录不存在: $Dir" }
if (-not (Test-Path -LiteralPath $TemplatePath -PathType Leaf)) { Fail "找不到模板文件: $TemplatePath" }

$workspace = (Resolve-Path -LiteralPath $Dir).Path
$template = [System.IO.File]::ReadAllText($TemplatePath, $Utf8NoBom)
# 统一行尾为 LF，与 build_viewer.py 的产出保持一致
$template = $template.Replace("`r`n", "`n").Replace("`r", "`n")

if ($template.IndexOf($Token) -lt 0) { Fail "模板缺少占位符 $Token" }

$payload = Build-Payload -Workspace $workspace

$blob = $payload | ConvertTo-Json -Depth 100 -Compress
# 破坏 </script>：HTML 解析器遇到 </script 即终止脚本块。
# \/ 是合法 JSON 转义，解析回来仍是 /，数据不受影响。
$blob = $blob.Replace('</', '<\/')

$html = $template.Replace($Token, $blob)

if ([string]::IsNullOrWhiteSpace($Out)) { $destination = Join-Path $workspace 'viewer.html' }
else { $destination = [System.IO.Path]::GetFullPath($Out) }

try {
    $parent = Split-Path -Parent $destination
    if ($parent -and -not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    [System.IO.File]::WriteAllText($destination, $html, $Utf8NoBom)
}
catch { Fail "写入失败 $destination ：$($_.Exception.Message)" }

$sizeKb = [math]::Round((Get-Item -LiteralPath $destination).Length / 1KB)
$chapterCount = @($payload.chapters).Count
Write-Host "已生成 $destination（$sizeKb KB，内嵌 $chapterCount 章）"
Write-Host '双击打开即可阅读；写了新章节就重新运行本脚本，再刷新页面。'

foreach ($notice in @($payload.notices)) {
    if ($null -ne $notice) { Write-Host "  [$($notice.level)] $($notice.message)" }
}

if ($Open) {
    Start-Process $destination
}
