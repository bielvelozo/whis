# Cria um atalho .lnk com a propriedade System.AppUserModel.ID.
#
# Um app não empacotado só consegue disparar toast se tiver um atalho no Menu
# Iniciar com essa propriedade, e o WScript.Shell não sabe gravá-la: é preciso
# abrir o .lnk como IPropertyStore. Este script é chamado por whis.automacao.
param(
    [Parameter(Mandatory = $true)][string]$Atalho,
    [Parameter(Mandatory = $true)][string]$Alvo,
    [Parameter(Mandatory = $true)][string]$Argumentos,
    [Parameter(Mandatory = $true)][string]$Diretorio,
    [Parameter(Mandatory = $true)][string]$Descricao,
    [Parameter(Mandatory = $true)][string]$Aumid
)

$ErrorActionPreference = "Stop"

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($Atalho)
$lnk.TargetPath = $Alvo
$lnk.Arguments = $Argumentos
$lnk.WorkingDirectory = $Diretorio
$lnk.Description = $Descricao
$lnk.Save()

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;

namespace WhisAtalho {
    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    public struct PropertyKey {
        public Guid fmtid;
        public uint pid;
        public PropertyKey(Guid f, uint p) { fmtid = f; pid = p; }
    }

    [StructLayout(LayoutKind.Explicit)]
    public struct PropVariant {
        [FieldOffset(0)] public ushort vt;
        [FieldOffset(8)] public IntPtr p;
    }

    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPropertyStore {
        void GetCount(out uint c);
        void GetAt(uint i, out PropertyKey k);
        void GetValue(ref PropertyKey k, out PropVariant v);
        void SetValue(ref PropertyKey k, ref PropVariant v);
        void Commit();
    }

    [ComImport, Guid("00021401-0000-0000-C000-000000000046")]
    public class ShellLink { }

    public static class Aumid {
        public static void Gravar(string caminho, string aumid) {
            var link = new ShellLink();
            var persist = (IPersistFile)link;
            persist.Load(caminho, 2);
            var store = (IPropertyStore)link;
            var chave = new PropertyKey(new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), 5);
            var valor = new PropVariant();
            valor.vt = 31;
            valor.p = Marshal.StringToCoTaskMemUni(aumid);
            try {
                store.SetValue(ref chave, ref valor);
                store.Commit();
                persist.Save(caminho, true);
            } finally {
                Marshal.FreeCoTaskMem(valor.p);
            }
        }
    }
}
"@

[WhisAtalho.Aumid]::Gravar($Atalho, $Aumid)
