<?php

function startsWith($a, $b) {
    return substr($a, 0, strlen($b)) == $b;
}

$map = file_get_contents('build/maple_mini.map');

$lines = explode("\n", $map);
$map = [];
foreach ($lines as $line) {
    $line = trim($line);
    $line = str_replace('.text', '', $line);
    for ($k=0; $k<10; $k++) {
        $line = str_replace('  ', ' ', $line);
    }
    $line = trim($line);
    $parts = explode(' ', $line);
    $addr = $parts[0];
    if (startsWith($line, '0x0000000008') && startsWith($parts[1], '0x') && isset($parts[2])) {
        $size = (int)hexdec(substr($parts[1], 2));
        $file = $parts[2];
        if (!isset($map[$file])) {
            $map[$file] = 0;
        }
        $map[$file] += $size;
    }
}
$total = 0;
foreach ($map as $file => $size) {
    echo "$size\t$file\n";
    $total += $size;
}
echo "Total: $total\n";