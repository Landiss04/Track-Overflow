# Re-export the Train Controller SDD figures from the design review deck.
#
# The deck is the source of every figure here: fix a slide in
# PowerPoint, then run this to refresh the PNGs the SDD links to.
# Slides are found by title, so reordering the deck changes nothing.
# Needs PowerPoint (opened read-only and hidden).
#
#   powershell -ExecutionPolicy Bypass -File export-slides.ps1 -Deck <path to .pptx>

param(
    [Parameter(Mandatory = $true)][string]$Deck,
    # 200 dpi on a 13.33 in slide, as the first export was.
    [int]$Width = 2667,
    [int]$Height = 1500
)

# Slide title -> file name. A title missing from the deck is reported,
# not guessed at.
$figures = [ordered]@{
    'System architecture'                          = '01-system-architecture.png'
    'Software architecture'                        = '02-software-architecture.png'
    'Use case diagram'                             = '03-use-case.png'
    'Class diagram: controller core'               = '04-class-controller-core.png'
    'Class diagram: State and exceptions'          = '05-class-state-exceptions.png'
    'Class diagram: console'                       = '06-class-console.png'
    'Sequence diagram'                             = '07-seq-00-one-tick.png'
    'Sequence diagram: Set target speed (Manual)'  = '07-seq-01-set-target-speed.png'
    'Sequence diagram: Switch Manual / Automatic'  = '07-seq-02-switch-mode.png'
    'Sequence diagram: Apply service brake'        = '07-seq-03-service-brake.png'
    'Sequence diagram: Open or close doors'        = '07-seq-04-doors.png'
    'Sequence diagram: Turn lights on or off'      = '07-seq-05-lights.png'
    'Sequence diagram: Set cabin temperature'      = '07-seq-06-cabin-temperature.png'
    'Sequence diagram: Announce station'           = '07-seq-07-announce.png'
    'Sequence diagram: Set Kp and Ki'              = '07-seq-08-set-gains.png'
    'Sequence diagram: Engage e-brake'             = '07-seq-09-engage-ebrake.png'
    'Sequence diagram: Release e-brake'            = '07-seq-10-release-ebrake.png'
}

$out = $PSScriptRoot
$deckPath = (Resolve-Path $Deck).Path
$pp = New-Object -ComObject PowerPoint.Application
try {
    # Read-only, untitled, no window.
    $p = $pp.Presentations.Open($deckPath, $true, $false, $false)
    $byTitle = @{}
    foreach ($s in $p.Slides) {
        if ($s.Shapes.HasTitle) {
            $byTitle[$s.Shapes.Title.TextFrame.TextRange.Text.Trim()] = $s
        }
    }
    foreach ($title in $figures.Keys) {
        $file = Join-Path $out $figures[$title]
        if ($byTitle.ContainsKey($title)) {
            $byTitle[$title].Export($file, 'PNG', $Width, $Height)
            "exported  {0}" -f $figures[$title]
        } else {
            "MISSING   '{0}' (no slide with that title)" -f $title
        }
    }
    $p.Close()
} finally {
    $pp.Quit()
}
