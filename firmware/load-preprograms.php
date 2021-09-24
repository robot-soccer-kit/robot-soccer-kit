<?php

// Checking for files to exist
if (!file_exists('build/maple_mini.map') || !file_exists('build/maple_mini.bin')) {
    echo "Error: build files does not exist!\n";
    exit(1);
}

// Checking for rhock_progs
$prog = trim(`cat build/maple_mini.map |grep ^rhock_progs`);

if (!$prog) {
    echo "Error: can't find rhock_progs address!\n";
    exit(1);
}

for ($i = 0; $i < 10; $i++) {
    $prog = str_replace('  ', ' ', $prog);
}
$parts = explode(' ', $prog);
$address = hexdec(substr($parts[1], 2)) - 0x08003000;
$size = hexdec(substr($parts[2], 2));

if ($address < 5000) {
    echo "Error: bad rhock_progs address!\n";
    exit(1);
}

// Doing the job
$pages = $size / 1024;
echo "Loading rhock programm at 0x" . sprintf("%x", $address) . ", $pages pages\n";
$binary = file_get_contents('build/maple_mini.bin');

function load_pgm($path)
{
    $data = file_get_contents($path);
    $parts = explode(' ', $data);
    $data = '';
    foreach ($parts as $n) {
        if ($n != '') {
            $data .= chr((int) $n);
        }
    }
    return $data;
}

echo "* Erasing pages\n";
for ($k = 0; $k < $pages; $k++) {
    for ($i = 0; $i < 1024; $i++) {
        $binary[$address + 1024 * $k + $i] = chr(0);
    }
}

$k = 0;
foreach (scandir('preprograms') as $file) {
    if ($file != '.' && $file != '..') {
        if ($k < $pages) {
            echo "* Loading preprogram $file into page $k...\n";
            $pgm = load_pgm('preprograms/' . $file);
            if (strlen($pgm > 1024)) {
                echo "! Warning: program $file size is greater than 1024\n";
            } else {
                for ($i = 0; $i < strlen($pgm); $i++) {
                    $binary[$address + 1024 * $k + $i] = $pgm[$i];
                }
            }
        }
        $k++;
    }
}

file_put_contents('build/maple_mini.bin', $binary);
