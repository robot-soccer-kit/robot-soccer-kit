#include "bin_stream.h"
#include "buzzer.h"
#include "kicker.h"
#include "leds.h"
#include "motors.h"
#include "shell.h"
#include "voltage.h"
#include "config.h"

#include <WiFi.h>
#include <WiFiUdp.h>
#include <ESP32Ping.h>

// Définir les informations du réseau WiFi
const char *ssid = "Wifi_RSK2";
const char *password = "26052005";

// Configuration de l'adresse IP statique et des paramètres réseau
IPAddress ip(32, 168, 2, 204);
IPAddress dns(192, 168, 1, 1);
IPAddress gateway(192, 168, 40, 1);
IPAddress subnet(255, 255, 255, 0);

// Configuration du port et de l'adresse du serveur UDP
unsigned int localPort = 9999;
const char *udpAddress = "255.255.255.255";
unsigned int udpPort = 9999;

// Variables pour UDP
WiFiUDP udp;
char packetBuffer[255];

void setupWifi()
{
  Serial.begin(115200);

  // Connexion au réseau WiFi
  Serial.println();
  Serial.print("[WiFi] Connecting to ");
  Serial.println(ssid);

  // Connexion au réseau WiFi
  WiFi.config(ip, gateway, subnet, dns);
  WiFi.begin(ssid, password);

  int tryDelay = 500;
  int numberOfTries = 20;

  while (WiFi.status() != WL_CONNECTED && numberOfTries > 0)
  {
    delay(tryDelay);
    Serial.print(F("."));
    numberOfTries--;
  }

  if (WiFi.status() == WL_CONNECTED)
  {
    Serial.println("\nConnected to the WiFi network : ");
    Serial.println(ssid);
    Serial.print("[+] ESP32 IP : ");
    Serial.println(WiFi.localIP());
    udp.begin(localPort);
    Serial.printf("UDP Client : %s:%i \n", WiFi.localIP().toString().c_str(), localPort);
  }
  if (numberOfTries <= 0)
  {
    Serial.print("[WiFi] Failed to connect to");
    Serial.println(ssid);
    WiFi.disconnect();
    return;
  }
  else
  {
    numberOfTries--;
  }
}

void loopWifi()
{
  // Vérifier l'état de connexion WiFi
  if (WiFi.status() != WL_CONNECTED)
  {
    int reconnectAttempts = 0;
    while (reconnectAttempts < 4)
    {
      Serial.println(" \n[WiFi] Disconnected, attempting to reconnect... Test " + String(reconnectAttempts + 1) + "/4");
      WiFi.disconnect();
      WiFi.begin(ssid, password);
      int tryDelay = 500;
      int numberOfTries = 20;

      while (WiFi.status() != WL_CONNECTED && numberOfTries > 0)
      {
        delay(tryDelay);
        Serial.print(F("."));
        numberOfTries--;
      }

      if (WiFi.status() == WL_CONNECTED)
      {

        Serial.println("\nReconnected to the WiFi network : ");
        Serial.println(ssid);
        Serial.print("[+] ESP32 IP : ");
        Serial.println(WiFi.localIP());
        break;
      }
      else
      {
        Serial.println("\nFailed to reconnect to WiFi network");
        reconnectAttempts++;
      }
    }
    // 4 tentatives de connexion max
    if (reconnectAttempts >= 4)
    {
      Serial.println("Failed to reconnect after 4 attempts.");
      WiFi.disconnect();
    }
  }

  // Lire les paquets UDP
  int packetSize = udp.parsePacket();
  if (packetSize)
  {
    int len = udp.read(packetBuffer, 255);
    if ((len > 0) && (len < 255))
    {
      packetBuffer[len] = 10; // Terminer la chaîne de caractères
      Serial.printf("Received packet: %s\n", packetBuffer);
    }
  }
  WiFi.setAutoReconnect(true);
}

IPAddress calculateNetworkAddress()
{
  IPAddress ip = WiFi.localIP();
  IPAddress subnet = WiFi.subnetMask();
  return IPAddress(ip[0] & subnet[0], ip[1] & subnet[1], ip[2] & subnet[2], ip[3] & subnet[3]);
}

// Commandes shell pour la gestion du WiFi
SHELL_COMMAND(wifi_status, "Status of the WiFi connection")
{
  Serial.println("\n");
  Serial.println("Informations réseau :");
  Serial.println("---------------------------------");
  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());
  Serial.print("Adresse réseau : ");
  Serial.println(calculateNetworkAddress());
  Serial.print("Force du signal (RSSI): ");
  Serial.println(WiFi.RSSI());
  Serial.print("Adresse MAC: ");
  Serial.println(WiFi.macAddress());
  Serial.print("Masque de sous-réseau: ");
  Serial.println(WiFi.subnetMask());
  Serial.print("Adresse IP de la passerelle: ");
  Serial.println(WiFi.gatewayIP());
  Serial.print("Adresse IP DNS: ");
  Serial.println(WiFi.dnsIP());
  Serial.println("---------------------------------");
  Serial.println();
  if (WiFi.status() == WL_CONNECTED)
  {

    Serial.println("Le robot est bien connecté au réseau WiFi.");
    Serial.print("Connecté à ");
    Serial.println(ssid);
    Serial.print("Adresse IP: ");
    Serial.println(WiFi.localIP());
  }
  else
  {
    Serial.println("Le robot n'est pas connecté au réseau WiFi.");

    return;
  }
}

SHELL_COMMAND(wifi_scan, "Scan for WiFi networks")
{
  int n = WiFi.scanNetworks();
  Serial.println("Scan done");
  if (n == 0)
  {
    Serial.println("No networks found");
  }
  else
  {
    Serial.print(n);
    Serial.println(" networks found");
    for (int i = 0; i < n; ++i)
    {
      Serial.print(i + 1);
      Serial.print(": ");
      Serial.print(WiFi.SSID(i));
      Serial.print(" (");
      Serial.print(WiFi.RSSI(i));
      Serial.print(")");
      Serial.println((WiFi.encryptionType(i) == WIFI_AUTH_OPEN) ? " " : "*");
      delay(10);
    }
  }
}

SHELL_COMMAND(ping, "Ping a specific IP address")
{
  if (argc != 1)
  {
    Serial.println("Usage: ping <ip>");
    return;
  }

  IPAddress ip;
  if (!WiFi.hostByName(argv[0], ip))
  {
    Serial.println("Ping failed: unknown host");
    return;
  }

  Serial.print("Ping en cours vers : ");
  Serial.print(argv[0]);
  Serial.print(" (");
  Serial.print(ip);
  Serial.println(")");

  bool success = Ping.ping(ip, 4); // Envoyer 4 paquets.
  if (success)
  {
    Serial.println("Ping ok !");
  }
  else
  {
    Serial.println("Ping error !");
  }
}

SHELL_COMMAND(wifi_config, "Configurer l'IP, le masque de sous-réseau et la passerelle")
{
  if (argc != 3)
  {
    Serial.println("Usage: wifi_config <ip> <subnet> <gateway>");
    return;
  }

  IPAddress ip, subnet, gateway;

  if (!ip.fromString(argv[0]) || !subnet.fromString(argv[1]) || !gateway.fromString(argv[2]))
  {
    Serial.println("Erreur de configuration : IP, masque de sous-réseau ou passerelle non valide");
    return;
  }

  Serial.print("Configuration du réseau avec IP: ");
  Serial.print(ip);
  Serial.print(", Masque de sous-réseau: ");
  Serial.print(subnet);
  Serial.print(", Passerelle: ");
  Serial.println(gateway);

  if (WiFi.config(ip, gateway, subnet))
  {
    Serial.println("Configuration du réseau réussie !");
  }
  else
  {
    Serial.println("Erreur de configuration du réseau !");
  }
}

SHELL_COMMAND(wifi_connect, "Configurer le SSID et le mot de passe du WiFi")
{
  if (argc != 2)
  {
    Serial.println("Usage: wifi_connect <ssid> <password>");
    return;
  }

  const char *ssid = argv[0];
  const char *password = argv[1];

  Serial.print("Configuration du WiFi avec SSID: ");
  Serial.print(ssid);
  Serial.println();

  WiFi.begin(ssid, password);
  delay(4000);
  int numberOfTries = 20;
  int tryDelay = 500;
  while (WiFi.status() != WL_CONNECTED && numberOfTries > 0)
  {
    delay(tryDelay);
    Serial.print(F("."));
    numberOfTries--;
  }
  if (WiFi.status() == WL_CONNECTED)
  {
    Serial.println("Connexion WiFi réussie !");
  }
  else
  {
    Serial.println("Erreur de connexion WiFi !");
  }
}
