$ErrorActionPreference = "Stop"

$dataDirectory = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\recipes"))
$sourcePath = Join-Path $dataDirectory "recipes.xlsx"
$outputPath = Join-Path $dataDirectory "recipes.csv"

if (-not (Test-Path -LiteralPath $sourcePath)) {
  throw "recipes.xlsx 파일을 찾을 수 없어요: $sourcePath"
}

$tempRoot = [System.IO.Path]::GetFullPath($env:TEMP)
$tempDirectory = [System.IO.Path]::GetFullPath((Join-Path $tempRoot ("dangdang-recipe-import-" + [guid]::NewGuid().ToString("N"))))

if (-not $tempDirectory.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "임시 폴더가 허용된 경로를 벗어났어요."
}

function Get-ColumnIndex([string]$cellReference) {
  $letters = $cellReference -replace "\d", ""
  $index = 0
  foreach ($letter in $letters.ToCharArray()) {
    $index = ($index * 26) + ([int][char]$letter - [int][char]'A' + 1)
  }
  return $index - 1
}

New-Item -ItemType Directory -Path $tempDirectory | Out-Null

try {
  & tar.exe -xf $sourcePath -C $tempDirectory
  if ($LASTEXITCODE -ne 0) { throw "recipes.xlsx 압축을 읽지 못했어요." }

  [xml]$sharedDocument = Get-Content -Raw -Encoding utf8 (Join-Path $tempDirectory "xl\sharedStrings.xml")
  $sharedNamespace = New-Object System.Xml.XmlNamespaceManager($sharedDocument.NameTable)
  $sharedNamespace.AddNamespace("s", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")
  $sharedStrings = @($sharedDocument.SelectNodes("//s:si", $sharedNamespace) | ForEach-Object {
    ($_.SelectNodes(".//s:t", $sharedNamespace) | ForEach-Object { $_.InnerText }) -join ""
  })

  [xml]$sheetDocument = Get-Content -Raw -Encoding utf8 (Join-Path $tempDirectory "xl\worksheets\sheet1.xml")
  $sheetNamespace = New-Object System.Xml.XmlNamespaceManager($sheetDocument.NameTable)
  $sheetNamespace.AddNamespace("s", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")
  $rows = @($sheetDocument.SelectNodes("//s:sheetData/s:row", $sheetNamespace))

  function Get-RowValues($row, [int]$width) {
    $values = [string[]]::new($width)
    foreach ($cell in $row.SelectNodes("./s:c", $sheetNamespace)) {
      $index = Get-ColumnIndex $cell.GetAttribute("r")
      if ($index -lt 0 -or $index -ge $width) { continue }

      $cellType = $cell.GetAttribute("t")
      $valueNode = $cell.SelectSingleNode("./s:v", $sheetNamespace)
      $value = ""
      if ($cellType -eq "s" -and $null -ne $valueNode) {
        $value = $sharedStrings[[int]$valueNode.InnerText]
      } elseif ($cellType -eq "inlineStr") {
        $value = ($cell.SelectNodes(".//s:t", $sheetNamespace) | ForEach-Object { $_.InnerText }) -join ""
      } elseif ($null -ne $valueNode) {
        $value = $valueNode.InnerText
      }
      $values[$index] = $value
    }
    return $values
  }

  $headerValues = Get-RowValues $rows[0] 13
  $records = foreach ($row in $rows | Select-Object -Skip 1) {
    $values = Get-RowValues $row $headerValues.Count
    $record = [ordered]@{}
    for ($index = 0; $index -lt $headerValues.Count; $index++) {
      $record[$headerValues[$index]] = $values[$index]
    }
    [pscustomobject]$record
  }

  $records | Export-Csv -LiteralPath $outputPath -NoTypeInformation -Encoding utf8
  Write-Output "Exported $($records.Count) recipes to $outputPath"
} finally {
  $resolvedTemp = [System.IO.Path]::GetFullPath($tempDirectory)
  if ((Test-Path -LiteralPath $resolvedTemp) -and $resolvedTemp.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
  }
}
