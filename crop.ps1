Add-Type -AssemblyName System.Drawing
$imgPath = "c:\Users\mscod\Desktop\site-paquistao\logo.png"
$outPath = "c:\Users\mscod\Desktop\site-paquistao\icon.png"

$img = [System.Drawing.Image]::FromFile($imgPath)
$size = [math]::Min($img.Width, $img.Height)

$x = [math]::Floor(($img.Width - $size) / 2)
$y = [math]::Floor(($img.Height - $size) / 2)

$rect = New-Object System.Drawing.Rectangle($x, $y, $size, $size)
$bmp = New-Object System.Drawing.Bitmap($size, $size)

$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$gfx.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$gfx.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

# Clear background to transparent
$gfx.Clear([System.Drawing.Color]::Transparent)

$gfx.DrawImage($img, (New-Object System.Drawing.Rectangle(0, 0, $size, $size)), $rect, [System.Drawing.GraphicsUnit]::Pixel)

$gfx.Dispose()
$img.Dispose()

$bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()

Write-Host "Logo recortado com sucesso para icon.png!"
