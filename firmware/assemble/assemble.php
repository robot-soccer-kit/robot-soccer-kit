<?php

if (count($argv) < 3) {
    echo "Syntax: assemble.php [bootloader.bin] [firmware.bin]\n";
}

$offset = 0x3000;

$bootloader = file_get_contents($argv[1]);
$firmware = file_get_contents($argv[2]);

$result = $bootloader;
while (strlen($result) < $offset) {
    $result .= chr(0);
}

$result .= $firmware;

echo $result;
