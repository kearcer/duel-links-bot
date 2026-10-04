#include <MsgBoxConstants.au3>
#include <AutoItConstants.au3>
#include <WinAPI.au3>
#include <ScreenCapture.au3>
#include <GDIPlus.au3>
#include "FastFind.au3"
#include "duelists.au3"
#include "events.au3"

Global $title = "[TITLE:Yu-Gi-Oh! DUEL LINKS]"
Global $DebugDir = @ScriptDir & "\debug"
Global $DebugScreenShot = $DebugDir & "\last-area-failure-screen"
Global $DebugAreaShot = $DebugDir & "\last-area-failure-tabs"
Global $DebugDuelistHitShot = $DebugDir & "\duelist-hit"
Global $AdbScreenshot = $DebugDir & "\adb-screen.png"
Global $StopRequested = False
Global $UseAdbBackend = False
Global $AdbPath = "adb"
Global $AdbSerial = ""
Global $AdbBitmap = 0
Global $AdbGdiStarted = False
Global $AdbExcludedAreas[0][4]
Global $GameHwnd = 0
Global $CaptureHwnd = _WinAPI_GetDesktopWindow()
Global $ClientX = 0
Global $ClientY = 0
Global $ClientWidth = 1280
Global $ClientHeight = 720
Global $LogicalClientWidth = 1280
Global $LogicalClientHeight = 720
Global $AdbBaseClientWidth = 720
Global $AdbBaseClientHeight = 1280
Global $world = 0
Global $timer = TimerInit()
Global $Loop  = True
Global $CheckGems = True
Global $auto_orb_reload = False
Global $sPaused = False
Global $winPos[4] = [0, 0, 0, 0]

Func Initialize_game_window()
	If Initialize_adb_backend() Then Return True

	$UseAdbBackend = False
	$LogicalClientWidth = 1280
	$LogicalClientHeight = 720
	$GameHwnd = WinGetHandle($title)
	If $GameHwnd = 0 Then
		Write_log("Game window not found: " & $title)
		Return False
	EndIf
	$winPos = WinGetPos($GameHwnd)
	If Not IsArray($winPos) Then
		Write_log("Game window position unavailable.")
		Return False
	EndIf
	Update_client_geometry()
	FFSetWnd($GameHwnd)
	Write_log("Game window bound: handle=" & $GameHwnd & " x=" & $winPos[0] & " y=" & $winPos[1] & " width=" & $winPos[2] & " height=" & $winPos[3] & " client=" & $ClientX & "," & $ClientY & " " & $ClientWidth & "x" & $ClientHeight)
	Return True
EndFunc

Func Initialize_adb_backend()
	$AdbPath = Find_adb_path()
	If $AdbPath = "" Then Return False
	$AdbSerial = ""
	Local $devices = Adb_run("devices")
	If @error Then Return False
	Local $lines = StringSplit(StringStripCR($devices), @LF, 1)
	Local $deviceCount = 0
	For $i = 1 To $lines[0]
		If StringRegExp($lines[$i], "^\S+\s+device$") Then
			$deviceCount += 1
			Local $device = StringSplit(StringStripWS($lines[$i], 3), " ", 2)
			$AdbSerial = $device[0]
		EndIf
	Next
	If $deviceCount <> 1 Then Return False

	DirCreate($DebugDir)
	$UseAdbBackend = True
	Local $size = Adb_run("shell wm size", True)
	If @error Or Not StringRegExp($size, "(\d+)x(\d+)", 0) Then Return False
	Local $match = StringRegExp($size, "(\d+)x(\d+)", 1)
	$ClientWidth = Number($match[0])
	$ClientHeight = Number($match[1])
	If $ClientWidth <> $AdbBaseClientWidth Or $ClientHeight <> $AdbBaseClientHeight Then
		$UseAdbBackend = False
		Write_log("ADB device found, but portrait resolution is " & $ClientWidth & "x" & $ClientHeight & ". MuMu should be set to 720x1280.")
		Return False
	EndIf
	$LogicalClientWidth = $AdbBaseClientWidth
	$LogicalClientHeight = $AdbBaseClientHeight
	$ClientX = 0
	$ClientY = 0
	$GameHwnd = 0
	$UseAdbBackend = True
	If Not $AdbGdiStarted Then
		_GDIPlus_Startup()
		$AdbGdiStarted = True
	EndIf
	AdbReleaseSnapshot()
	Write_log("MuMu connected automatically: " & $ClientWidth & "x" & $ClientHeight)
	Return True
EndFunc

Func Find_adb_path()
	Local $candidates[5] = [EnvGet("DLBOT_ADB"), @ScriptDir & "\adb.exe", @ScriptDir & "\platform-tools\adb.exe", "E:\Android\android-sdk\platform-tools\adb.exe", "adb"]
	For $i = 0 To UBound($candidates) - 1
		If $candidates[$i] = "" Then ContinueLoop
		If $candidates[$i] = "adb" Or FileExists($candidates[$i]) Then Return $candidates[$i]
	Next
	Return ""
EndFunc

Func Adb_run($arguments, $useSerial = False)
	Local $outputFile = $DebugDir & "\adb-command-output.txt"
	Local $prefix = '"' & $AdbPath & '"'
	If $useSerial And $AdbSerial <> "" Then $prefix &= ' -s "' & $AdbSerial & '"'
	Local $cmd = $prefix & " " & $arguments & ' > "' & $outputFile & '" 2>&1'
	Local $exitCode = RunWait(@ComSpec & " /c " & $cmd, @ScriptDir, @SW_HIDE)
	Local $output = ""
	If FileExists($outputFile) Then $output = FileRead($outputFile)
	If $exitCode <> 0 Then Return SetError(1, $exitCode, StringStripWS($output, 3))
	Return StringStripWS($output, 3)
EndFunc

Func Adb_shell($command)
	Local $prefix = '"' & $AdbPath & '"'
	If $AdbSerial <> "" Then $prefix &= ' -s "' & $AdbSerial & '"'
	Local $outputFile = $DebugDir & "\adb-shell-output.txt"
	Local $cmd = $prefix & " shell " & $command & ' > "' & $outputFile & '" 2>&1'
	Local $exitCode = RunWait(@ComSpec & " /c " & $cmd, @ScriptDir, @SW_HIDE)
	Local $output = ""
	If FileExists($outputFile) Then $output = FileRead($outputFile)
	If $exitCode <> 0 Then Return SetError(1, $exitCode, StringStripWS($output, 3))
	Return StringStripWS($output, 3)
EndFunc

Func Adb_exec_out_to_file($command, $path)
	Local $prefix = '"' & $AdbPath & '"'
	If $AdbSerial <> "" Then $prefix &= ' -s "' & $AdbSerial & '"'
	Local $cmd = $prefix & " exec-out " & $command & ' > "' & $path & '"'
	Local $exitCode = RunWait(@ComSpec & " /c " & $cmd, @ScriptDir, @SW_HIDE)
	If $exitCode <> 0 Or Not FileExists($path) Then Return SetError(1, $exitCode, False)
	Return True
EndFunc

Func AdbReleaseSnapshot()
	If $AdbBitmap <> 0 Then
		_GDIPlus_BitmapDispose($AdbBitmap)
		$AdbBitmap = 0
	EndIf
EndFunc

Func AdbCaptureSnapshot()
	If Not $UseAdbBackend Then Return False
	DirCreate($DebugDir)
	AdbReleaseSnapshot()
	If Not Adb_exec_out_to_file("screencap -p", $AdbScreenshot) Then
		Write_log("ADB screencap failed. Check emulator ADB connection.")
		Return False
	EndIf
	$AdbBitmap = _GDIPlus_BitmapCreateFromFile($AdbScreenshot)
	If $AdbBitmap = 0 Then
		Write_log("ADB screencap could not be decoded: " & $AdbScreenshot)
		Return False
	EndIf
	Return True
EndFunc

Func AdbTap($x, $y, $clicks)
	For $i = 1 To $clicks
		Adb_shell("input tap " & Int($x) & " " & Int($y))
		If $i < $clicks Then Sleep(120)
	Next
EndFunc

Func ToBackendX($x)
	Return Int(($x * $ClientWidth) / $LogicalClientWidth)
EndFunc

Func ToBackendY($y)
	Return Int(($y * $ClientHeight) / $LogicalClientHeight)
EndFunc

Func FromBackendX($x)
	Return Int(($x * $LogicalClientWidth) / $ClientWidth)
EndFunc

Func FromBackendY($y)
	Return Int(($y * $LogicalClientHeight) / $ClientHeight)
EndFunc

Func Refresh_game_window()
	If $UseAdbBackend Then Return True
	If $GameHwnd = 0 Or Not WinExists($GameHwnd) Then
		Return Initialize_game_window()
	EndIf
	$winPos = WinGetPos($GameHwnd)
	If Not IsArray($winPos) Then Return False
	Update_client_geometry()
	FFSetWnd($GameHwnd)
	Return True
EndFunc

Func Update_client_geometry()
	Local $clientSize = WinGetClientSize($GameHwnd)
	If IsArray($clientSize) Then
		$ClientWidth = $clientSize[0]
		$ClientHeight = $clientSize[1]
	EndIf
	Local $clientPoint = DllStructCreate($tagPOINT)
	_WinAPI_ClientToScreen($GameHwnd, $clientPoint)
	If @error Then
		$ClientX = $winPos[0]
		$ClientY = $winPos[1]
		Return False
	EndIf
	$ClientX = DllStructGetData($clientPoint, "X")
	$ClientY = DllStructGetData($clientPoint, "Y")
	Return True
EndFunc

Func Sleep_checked($milliseconds)
	Local $timer = TimerInit()
	While TimerDiff($timer) < $milliseconds
		If Is_stop_requested() Then Return -1
		Sleep(100)
	WEnd
	Return 0
EndFunc

Func Request_stop()
	$StopRequested = True
	$Loop = False
	$sPaused = False
	Write_log("Stop requested.")
EndFunc

Func Is_stop_requested()
	Control_gui(GUIGetMsg())
	Return $StopRequested
EndFunc

#cs
	Gate duel using the first character that appears
	; Click(902, 372) ;next legendary duelist
#ce
Func Gate_duel($amount)
   If Is_stop_requested() Then Return
   If Go_to_area(0) == -1 Then Return
   For $i = 0 To $amount Step 1
		If Is_stop_requested() Then Return
		Click(727, 341)
		Write_log("Click duel gate.")
		Wait_pixel(626, 743, 0xFFFFFF, 10000, "Legendary Duelist list")
		Wait_pixel(632, 654, 0xF8D627, 10000, "Duel text golden color")
		Click(632, 654)
		Write_log("Du-du-du-el")
		letsDuel()
		Sleep(200)
	Next
EndFunc   ;==>Gate_duel

#cs
Duel any steet duelist availbae at $world(0 for Yu-Gi-Oh and 1 for
	Yu-Gi-Oh GX) starting from $start_area
#ce
Func Street_duel($world, $start_area)
	If Is_stop_requested() Then Return
	$duelist = Get_duelists($world)

	For $area = $start_area To 3 Step 1
		If Is_stop_requested() Then Return
		Do
			If Is_stop_requested() Then Return
			Local $hSearch = Search($area, 99)
			Switch $hSearch
				Case -1
					Return
				Case 1
					Write_log("Loot detected")
					$message = "Receive Rewards"
					Wait_pixel(500, 460, 0xFFFFFF, 5000, $message)
					Write_log($message)
					Sleep(1000)
					Click(640, 460)
					Sleep(500)
			EndSwitch
		Until $hSearch == 0
		Write_log("Area is clear from loot")

		For $char = 0 To UBound($duelist) - 1 Step 1
			If Is_stop_requested() Then Return
			Switch Search($area, $duelist[$char])
				Case -1
					Return
				Case 1
					 If letsDuel() == 1 Then
					   Sleep(200)
					   If Compare_pixel(637, 394, 0xFFFFFF) == 1 Then
						   Write_log('Collect fragments')
						   Click(642, 425)
					   Else
						   If Compare_pixel(596, 427, 0x8C0606) == 1 Then
							   vagabond_challange()
						   EndIf
					   EndIf

					   Sleep(700)
						Auto_orb()
					   $char = 0
					 EndIf
			EndSwitch
		Next
		Write_log("No one here.")

		; Additional routines
		If $CheckGems Then
			Grant_gems($area)
		EndIf
		If $auto_orb_reload Then
			Auto_orb()
		EndIf

		If $Loop And $area == 3 Then
			$area = -1
		EndIf
	Next
	Write_log("Street duel over")
	Return
 EndFunc   ;==>Street_duel

Func Auto_orb()
   If Compare_pixel(456, 68, 0x6666AA) == 1 And Compare_pixel(456, 77, 0x6666AA) == 1 Then
	  Write_log('Duel beacon, Standard duelist depleted.')
	  If $auto_orb_reload Then
		 Click(400, 75)

		 $massage = "Use Duel beacon"
		 Write_log($massage)
		 Wait_pixel(569, 179, 0xFFCC00, 10000, $massage)
		 Click(600, 240)

		 $massage = "Confirm"
		 Write_log($massage)
		 Wait_pixel(515, 430, 0x870505, 10000, $massage)
		 Click(700, 430)
		 Sleep(2000)
		 Click(700, 430)
		 Sleep(1000)
	  Else
		 Write_log('Orb auto reload disabled.')
	  EndIf
   EndIf
EndFunc

Func Grant_gems($area)
	Write_log("Granting gems")
	Switch $area
	  Case 0
		 Click(650, 360)
		 Handle_gems_dialog()
	  Case 1
		 Click(800, 455)
		 Handle_gems_dialog()
	  Case 2
		 Click(600, 300)
		 Handle_gems_dialog()
	  Case 3
		 Click(560, 580)
		 Handle_gems_dialog()
	EndSwitch
 EndFunc

Func Handle_gems_dialog()
   	If Wait_pixel(500, 400, 0xFFFFFF, 8000, 'Waiting gems') == 0 And Wait_pixel(780, 400, 0xFFFFFF, 500, 'Waiting gems') == 0 Then
		Click(650, 480)
		Sleep(2000)
	EndIf
EndFunc

; Checks if gems balance is visible at the top
Func Has_gems_balance_visible()
	Return Compare_pixel(855, 76, 0x9453AB) == 1 And Compare_pixel(861, 69, 0x09F7F0) == 1
EndFunc


#cs
Duel with Autowin Skipped duel cheat. Precondition is starting duel dialog.

                 ___====-_  _-====___
           _--^^^#####//      #####^^^--_
        _-^##########// (    ) ##########^-_
       -############//  |^^/|  ############-
     _/############//   (@::@)   ############_
    /#############((     //     ))#############
   -###############    (oo)    //###############-
  -#################  / VV   //#################-
 -###################/      //###################-
_#/|##########/######(   /   )######/##########|#_
|/ |#/#/#//  #/##  |  |  /##/#/  /#/#/#| |
`  |/  V  V  `   V  #| |  | |/#/  V   '  V  V  |  '
   `   `  `      `   / | |  | |    '      '  '   '
                    (  | |  | |  )
                   __ | |  | | /__
                  (vvv(VVV)(VVV)vvv)


Lalalalala
#ce
Func letsDuel()
	If Is_stop_requested() Then Return 0
	Local $massage
	Local $time_out
	Local $count = 0

   Sleep(1000)
   If has_white_dialog() Then
	  While has_white_dialog()
		 Write_log("Reading dialog")
		 Click(700, 653)
		 Sleep(1000)
	  WEnd
   Else
	  Write_log("No white dialog")
	  If $world = 7 Then
		Sleep(7000) ; Yu-gi-oh Sevens is so damn slow
	  Else
		Sleep(3000)
	  EndIf

	  ; Confirm there's a duel screen
	  If has_duel_screen() Then
		 Write_log("Duel screen found")
	  Else
	    Write_log("No duel screen, skipping")
		Return 0;
	  EndIf
   EndIf

   ; Start auto duel
   Click(700, 653)
   Sleep(1000)
   Click(700, 653)
   Write_log("Duel Started!")
   Sleep(10000)

	; Wait for duel end
    $time_out = 300000
	$timer = TimerInit()
	While (TimerDiff($timer) < $time_out) And (get_area(0) == -1)
	   If Is_stop_requested() Then Return 0
	   While (TimerDiff($timer) < $time_out) And (get_area(0) == -1)
		   If Is_stop_requested() Then Return 0
		   Click(644, 708);
		   vagabond_challange()
		   $count += 1
		   If Mod($count, 10) = 0 Then
				Write_log("Waiting Duel")
		   EndIf
		   Sleep(1000)
	   WEnd
	   Sleep(3000)
    WEnd
    Write_log("Duel Finished")
	WriteTimeout($timer, $time_out)
	CloseDialogue()

	Return 1;
EndFunc   ;==>letsDuel

Func CloseDialogue()
	Write_log("Exit Dialogue")
	Sleep(1000)

	$time_out = 5000
	$timer = TimerInit()
	While Compare_pixel(640, 736, 0xFFFFFF) == 1 And (TimerDiff($timer) < $time_out)
		Click(644, 708)
		Sleep(1000)
	WEnd
	;WriteTimeout($timer, $time_out)
EndFunc  ;==>CloseDialogue

Func WriteTimeout($timer, $time_out)
	If Is_stop_requested() Then Return
	If TimerDiff($timer) >= $time_out Then
		$time_out = 5000
		Write_log("Time out!")
		Write_log("Exit in " & $time_out / 1000 & " s")
		Sleep_checked($time_out)
		Exit
	Else
		Write_log(time_s(TimerDiff($timer)) & " s")
	EndIf
EndFunc

#cs
	Vagabond introduce. Set second name in the list and choose one opening hand as challange
#ce
Func vagabond_challange()
   If Compare_pixel(520, 380, 0xFFFFFF) == 1 AND Compare_pixel(780, 380, 0xFFFFFF) == 1 Then
	  Sleep(1000)
	  If Compare_pixel(520, 380, 0xFFFFFF) == 1 AND Compare_pixel(780, 380, 0xFFFFFF) == 1 Then
		  Write_log('Decline to check oponent deck')
		  Click(550, 430)
	  EndIf
	EndIf
EndFunc   ;==>vagabond_challange

#cs
	Search $object insinde $area
#ce
Func Search($area, $object)
	If Is_stop_requested() Then Return -1
	If Go_to_area($area) == -1 Then
		Return -1
	EndIf
	Duel_world_exclude_area($area)

	Local $found
	Local $hObject = Object_color($object)
	Local $searchLeft = 0
	Local $searchTop = 0
	Local $searchRight = $LogicalClientWidth - 1
	Local $searchBottom = $LogicalClientHeight - 1
	Local $pos
	If $UseAdbBackend Then
		SnapShot(0, 0, 0, 0)
		$pos = AdbBestSpot($hObject[1], $searchLeft, $searchTop, $searchRight, $searchBottom)
	Else
		FFAddColor($hObject[1])
		$pos = FFBestSpot(10, 7, 16, 632, 488, -1, 2, True, $searchLeft, $searchTop, $searchRight, $searchBottom)
	EndIf

	If IsArray($pos) Then
		Write_log("Seems like " & $hObject[0] & ", " & $pos[2] & " pixel detected.")
		Save_duelist_hit_debug_snapshot($hObject[0], $pos, 10)
		ClickOn($pos[0], $pos[1], 2)
		$found = 1
	Else
		$found = 0
	EndIf
	If $UseAdbBackend Then
		AdbResetExcludedAreas()
	Else
		FFResetColors()
		FFResetExcludedAreas()
	EndIf
	Return $found
EndFunc   ;==>Search

Func AdbBestSpot($colors, $left, $top, $right, $bottom)
	If $AdbBitmap = 0 Then Return SetError(1, 0, 0)
	Local $best[3] = [-1, -1, 0]
	For $y = $top To $bottom Step 2
		For $x = $left To $right Step 2
			If AdbIsExcluded($x, $y) Then ContinueLoop
			Local $pixel = _GDIPlus_BitmapGetPixel($AdbBitmap, ToBackendX($x), ToBackendY($y))
			For $i = 0 To UBound($colors) - 1
				If ColorNear($pixel, $colors[$i], 24) Then
					Local $score = AdbColorScore($x, $y, $colors)
					If $score > $best[2] Then
						$best[0] = $x
						$best[1] = $y
						$best[2] = $score
					EndIf
					ExitLoop
				EndIf
			Next
		Next
	Next
	If $best[2] >= 4 Then Return $best
	Return SetError(1, 0, 0)
EndFunc

Func AdbColorScore($centerX, $centerY, $colors)
	Local $score = 0
	For $y = $centerY - 5 To $centerY + 5 Step 2
		If $y < 0 Or $y >= $LogicalClientHeight Then ContinueLoop
		For $x = $centerX - 5 To $centerX + 5 Step 2
			If $x < 0 Or $x >= $LogicalClientWidth Or AdbIsExcluded($x, $y) Then ContinueLoop
			Local $pixel = _GDIPlus_BitmapGetPixel($AdbBitmap, ToBackendX($x), ToBackendY($y))
			For $i = 0 To UBound($colors) - 1
				If ColorNear($pixel, $colors[$i], 24) Then
					$score += 1
					ExitLoop
				EndIf
			Next
		Next
	Next
	Return $score
EndFunc

Func ColorNear($actual, $expected, $tolerance)
	Local $ar = BitAND(BitShift($actual, 16), 0xFF)
	Local $ag = BitAND(BitShift($actual, 8), 0xFF)
	Local $ab = BitAND($actual, 0xFF)
	Local $er = BitAND(BitShift($expected, 16), 0xFF)
	Local $eg = BitAND(BitShift($expected, 8), 0xFF)
	Local $eb = BitAND($expected, 0xFF)
	Return Abs($ar - $er) <= $tolerance And Abs($ag - $eg) <= $tolerance And Abs($ab - $eb) <= $tolerance
EndFunc

Func AdbIsExcluded($x, $y)
	For $i = 0 To UBound($AdbExcludedAreas) - 1
		If $x >= $AdbExcludedAreas[$i][0] And $x <= $AdbExcludedAreas[$i][2] And $y >= $AdbExcludedAreas[$i][1] And $y <= $AdbExcludedAreas[$i][3] Then Return True
	Next
	Return False
EndFunc

Func AdbResetExcludedAreas()
	ReDim $AdbExcludedAreas[0][4]
EndFunc

Func Move($x, $y)
	If Not Refresh_game_window() Then Return
	If $UseAdbBackend Then
		AdbTap(ToBackendX($x), ToBackendY($y), 1)
		Return
	EndIf
	MouseMove($x + $ClientX, $y + $ClientY, 0)
EndFunc   ;==>Move

#cs
	Do a single mouse click at ($x,$y)
#ce
Func Click($x, $y)
	If $x >= 0 And $x < $LogicalClientWidth And $y >= 0 And $y < $LogicalClientHeight Then
		ClickOn($x, $y, 1)
	Else
		Write_log("Blocked out-of-game click at " & $x & ", " & $y)
	EndIf
EndFunc   ;==>Click


#cs
	Wrap MouseClick
#ce
Func ClickOn($x, $y, $clicks)
	If Not Refresh_game_window() Then Return
	If $x < 0 Or $x >= $LogicalClientWidth Or $y < 0 Or $y >= $LogicalClientHeight Then
		Write_log("Blocked out-of-game click at " & $x & ", " & $y)
		Return
	EndIf
	If $UseAdbBackend Then
		AdbTap(ToBackendX($x), ToBackendY($y), $clicks)
		Return
	EndIf
	MouseClick($MOUSE_CLICK_LEFT, $x + $ClientX, $y + $ClientY, $clicks)
EndFunc   ;==>ClickOn

#cs
	Take SnapShot of current screen. Refer to FastFind.chm for information
#ce
Func SnapShot($x1, $y1, $x2, $y2)
	If Not Refresh_game_window() Then Return
	If $UseAdbBackend Then
		AdbCaptureSnapshot()
		Return
	EndIf
	Local $left = $ClientX + $x1
	Local $top = $ClientY + $y1
	Local $right = $ClientX + $x2
	Local $bottom = $ClientY + $y2
	If $x1 = 0 And $y1 = 0 And $x2 = 0 And $y2 = 0 Then
		$left = $ClientX
		$top = $ClientY
		$right = $ClientX + $ClientWidth
		$bottom = $ClientY + $ClientHeight
	EndIf
	FFSnapShot($left, $top, $right, $bottom, $FFDefaultSnapShot, $CaptureHwnd)
EndFunc   ;==>SnapShot

#cs
	return color of pixel at ($x,$y)
#ce
Func GetPixel($x, $y)
	SnapShot(0, 0, 0, 0)
	If $UseAdbBackend Then
		If $AdbBitmap = 0 Then Return 0
		Return _GDIPlus_BitmapGetPixel($AdbBitmap, ToBackendX($x), ToBackendY($y))
	EndIf
	Return FFGetPixel($x, $y)
EndFunc   ;==>GetPixel

#cs
	Add exclude zone inside rectangle that defined by two coordinate
	($x1, $y1) and  ($x2, $y2)
#ce
Func AdbGetPixelFromCurrentSnapshot($x, $y)
	If $AdbBitmap = 0 Then Return 0
	Return _GDIPlus_BitmapGetPixel($AdbBitmap, ToBackendX($x), ToBackendY($y))
EndFunc

Func AddExcludedArea($x1, $y1, $x2, $y2)
	Refresh_game_window()
	If $UseAdbBackend Then
		Local $count = UBound($AdbExcludedAreas)
		ReDim $AdbExcludedAreas[$count + 1][4]
		$AdbExcludedAreas[$count][0] = $x1
		$AdbExcludedAreas[$count][1] = $y1
		$AdbExcludedAreas[$count][2] = $x2
		$AdbExcludedAreas[$count][3] = $y2
		Return
	EndIf
	FFAddExcludedArea($x1, $y1, $x2, $y2)
EndFunc   ;==>AddExcludedArea

#cs
	Return current area code
	0:Gate
	1:Duel
	2:Shop
	3:Studio
	4:Initial Screen
#ce
Func get_area($force)
	Local $active_tab = get_active_tab()
	If $active_tab <> -1 Then
		Return $active_tab
	EndIf

	; Keep the old gems check as a diagnostic, but do not require it because newer UI colors can differ.
	If Has_gems_balance_visible() Then
		Write_log("Gems balance is visible, but active tab was not detected.")
	EndIf

	; Check if we are in the initial screen
	If initial_screen() Then
		Write_log("Initial screen, starting game")
		Click(650, 470)
		Sleep(10000)
		Return 4
	EndIf

	If $force == 1 Then
		; Keep searching, Bot is lost
		If Has_gems_balance_visible() Then
			Write_log("Gems balance is visible, but Bot is lost...")
		EndIf
		Write_log("Area can't be decided.")
		Write_log("Make sure four area tab is visible.")
		Close_open_menu()
		Sleep(3000)
		Return get_area($force)
	EndIf

	Return -1
EndFunc   ;==>get_area


#cs
	Return current area code
	0:Gate
	1:Duel
	2:Shop
	3:Studio
	-1:Not found

	Debug:
		Write_log("Area1 " & $area1 & " at " &$pos1[0]&" & "&$pos1[1])
		Write_log("Area2 " & $area2 & " at " &$pos2[0]&" & "&$pos2[1])
#ce
Func get_active_tab()
	SnapShot(0, 0, 0, 0)
	If $UseAdbBackend Then
		Local $area = get_active_tab_by_blue_score()
		If $area <> -1 Then Return $area
		Save_area_debug_snapshot()
		Return -1
	EndIf
	Local $pos1 = FFBestSpot(7, 4, 9, 655, 710, 0x001AFF, 10, False, 0, 0, $LogicalClientWidth - 1, $LogicalClientHeight - 1)
	Local $pos2 = FFBestSpot(7, 4, 9, 655, 710, 0x0012FF, 10, False, 0, 0, $LogicalClientWidth - 1, $LogicalClientHeight - 1)

	If IsArray($pos1) And IsArray($pos2) Then
		$area1 = get_identified_area($pos1, $winPos)
		$area2 = get_identified_area($pos2, $winPos)

		If $area1 == $area2 Then
			;Write_log("Area1 " & $area1 & " at " &$pos1[0]&" & "&$pos1[1])
			;Write_log("Area2 " & $area2 & " at " &$pos2[0]&" & "&$pos2[1])
			Return $area1
		Else
			Write_log("Area can't be decided. Conflict.")
		EndIf
	EndIf

	Local $area = get_active_tab_by_blue_score()
	If $area <> -1 Then
		Return $area
	EndIf

	Save_area_debug_snapshot()
	Return -1
EndFunc

Func get_active_tab_by_blue_score()
	Local $scores[4] = [0, 0, 0, 0]
	Local $xStarts[4] = [392, 519, 647, 764]
	Local $xEnds[4] = [500, 634, 741, 914]
	Local $winPosNow = WinGetPos($GameHwnd)
	Local $xOffset = 0
	Local $yOffset = 0

	If IsArray($winPosNow) Then
		$winPos = $winPosNow
	EndIf

	; Reuse the full-client snapshot created by get_active_tab().
	For $area = 0 To 3
		For $x = $xStarts[$area] + $xOffset To $xEnds[$area] + $xOffset Step 2
			For $y = 650 + $yOffset To 719 + $yOffset Step 2
				Local $color
				If $UseAdbBackend Then
					$color = AdbGetPixelFromCurrentSnapshot($x, $y)
				Else
					$color = FFGetPixel($x, $y, 0)
				EndIf
				If Is_blue_ui_pixel($color) Then
					$scores[$area] += 1
				EndIf
			Next
		Next
	Next

	Local $bestArea = -1
	Local $bestScore = 0
	Local $secondScore = 0
	For $area = 0 To 3
		If $scores[$area] > $bestScore Then
			$secondScore = $bestScore
			$bestScore = $scores[$area]
			$bestArea = $area
		ElseIf $scores[$area] > $secondScore Then
			$secondScore = $scores[$area]
		EndIf
	Next

	Write_log("Tab blue scores: " & $scores[0] & "," & $scores[1] & "," & $scores[2] & "," & $scores[3] & " offsets=" & $xOffset & "," & $yOffset)
	If $bestScore >= 8 And $bestScore >= ($secondScore * 2) Then
		Return $bestArea
	EndIf
	Return -1
EndFunc

Func Is_blue_ui_pixel($color)
	Local $red = BitAND(BitShift($color, 16), 0xFF)
	Local $green = BitAND(BitShift($color, 8), 0xFF)
	Local $blue = BitAND($color, 0xFF)
	Return $blue > 150 And $blue > ($red * 1.8) And $blue > ($green * 1.4)
EndFunc

Func Save_area_debug_snapshot()
	If Not Refresh_game_window() Then Return
	DirCreate($DebugDir)
	Local $screenPath = $DebugScreenShot & "-screen-" & @YEAR & @MON & @MDAY & "-" & @HOUR & @MIN & @SEC & ".jpg"
	Local $tabsPath = $DebugAreaShot & "-screen-" & @YEAR & @MON & @MDAY & "-" & @HOUR & @MIN & @SEC & ".jpg"
	If $UseAdbBackend Then
		If $AdbBitmap = 0 Then AdbCaptureSnapshot()
		FileCopy($AdbScreenshot, $screenPath, 9)
		Local $tabsPng = $DebugAreaShot & "-screen-" & @YEAR & @MON & @MDAY & "-" & @HOUR & @MIN & @SEC & ".png"
		Adb_exec_out_to_file("screencap -p", $tabsPng)
		Write_log("Area debug screenshots saved to " & $DebugDir & " screen=" & $screenPath & " adb=" & $AdbScreenshot)
		Return
	EndIf
	_ScreenCapture_Capture($screenPath, $ClientX, $ClientY, $ClientX + $ClientWidth - 1, $ClientY + $ClientHeight - 1, False)
	_ScreenCapture_Capture($tabsPath, $ClientX + 372, $ClientY + 650, $ClientX + 914, $ClientY + 719, False)
	Write_log("Area debug screenshots saved to " & $DebugDir & " screen=" & $screenPath & " tabs=" & $tabsPath)
EndFunc

Func Save_duelist_hit_debug_snapshot($name, $pos, $size)
	If Not IsArray($pos) Then Return
	If Not Refresh_game_window() Then Return
	DirCreate($DebugDir)

	Local $half = Int($size / 2)
	Local $left = $pos[0] - $half
	Local $top = $pos[1] - $half
	Local $right = $left + $size - 1
	Local $bottom = $top + $size - 1

	If $left < 0 Then $left = 0
	If $top < 0 Then $top = 0
	If $right >= $ClientWidth Then $right = $ClientWidth - 1
	If $bottom >= $ClientHeight Then $bottom = $ClientHeight - 1
	If $right < $left Or $bottom < $top Then Return

	Local $safeName = StringRegExpReplace($name, '[^0-9A-Za-z_-]', '_')
	Local $path = $DebugDuelistHitShot & "-" & @YEAR & @MON & @MDAY & "-" & @HOUR & @MIN & @SEC & "-" & $safeName & "-x" & $pos[0] & "-y" & $pos[1] & "-match" & $pos[2] & ".jpg"
	If $UseAdbBackend Then
		Local $adbPath = $DebugDuelistHitShot & "-" & @YEAR & @MON & @MDAY & "-" & @HOUR & @MIN & @SEC & "-" & $safeName & "-x" & $pos[0] & "-y" & $pos[1] & "-match" & $pos[2] & ".png"
		Adb_exec_out_to_file("screencap -p", $adbPath)
		Write_log("Duelist hit debug screenshot saved from ADB: " & $adbPath & " crop=" & $left & "," & $top & "," & $right & "," & $bottom)
		Return
	EndIf
	_ScreenCapture_Capture($path, $ClientX + $left, $ClientY + $top, $ClientX + $right, $ClientY + $bottom, False)
	Write_log("Duelist hit debug screenshot saved: " & $path & " crop=" & $left & "," & $top & "," & $right & "," & $bottom)
EndFunc
Func initial_screen()
	Local $initial_screen_pixels[26][3] = [[441, 121, 0xE20011], [455, 121, 0xEE0011], [446, 150, 0xD70000], [447, 170, 0xDD0000], [486, 193, 0xEE0011], [502, 158, 0xFFFFFF], [491, 126, 0xFFFFFF], [500, 137, 0xFFFFFF], [513, 128, 0xFFFFFF], [522, 108, 0x333333], [530, 146, 0xFFFFFF], [559, 151, 0xFFFFFF], [597, 129, 0xFFFFFF], [612, 165, 0xFFFFFF], [641, 147, 0xFFFFFF], [663, 133, 0xFFFFFF], [661, 115, 0xFFFFFF], [686, 97, 0xEE0011], [697, 172, 0xEE0011], [709, 156, 0xFFFFFF], [741, 142, 0xFFFFFF], [767, 125, 0xFFFFFF], [797, 150, 0xFFFFFF], [790, 104, 0xDE0011], [778, 73, 0xE7E7E7], [778, 84, 0xEE0011]]

	Return Compare_pixels($initial_screen_pixels)
EndFunc

Func Close_open_menu()
	; Check for back and home button
	Local $pixels[10][3] = [[403, 726, 0xFFFFFF], [417, 725, 0xFFFFFF], [424, 726, 0xFFFFFF], [398, 724, 0xFFFFFF], [403, 719, 0xFFFFFF], [403, 730, 0xFFFFFF], [396, 732, 0x02338D], [395, 714, 0x002264], [422, 714, 0x002264], [422, 732, 0x003396]]

	If Compare_pixels($pixels) Then
		Write_log("Going back home")
		Click(400, 725) ;home button
	EndIf
EndFunc

#cs
	Return current area code
	0:Gate
	1:Duel
	2:Shop
	3:Studio
#ce
Func get_identified_area($pos, $winPos)
	Local $area = -1
	Switch $pos[0]
		Case 392 To 500
			$area = 0
		Case 519 To 634
			$area = 1
		Case 647 To 741
			$area = 2
		Case 764 To 868
			$area = 3
	EndSwitch
	Return $area
EndFunc   ;==>get_identified_area

#cs
	Go to $des_area
#ce
Func Go_to_area($des_area)
	If Is_stop_requested() Then Return -1
	Local $cur_area = get_area(1)
	If Is_stop_requested() Then Return -1
	If $cur_area <> $des_area Then
		If $cur_area == -1 Then
			Return -1
		EndIf
		Local $massage = ""
		Select
			Case $des_area = 0
				Click(463, 722)
				$massage = "Go to Gate area"
				If Sleep_checked(800) = -1 Then Return -1
			Case $des_area = 1
				Click(592, 721)
				$massage = "Go to Duel area"
				If Sleep_checked(800) = -1 Then Return -1
			Case $des_area = 2
				Click(710, 722)
				$massage = "Go to Shop area"
				If Sleep_checked(800) = -1 Then Return -1
			Case $des_area = 3
				Click(835, 722)
				$massage = "Go to Studio area"
				If Sleep_checked(800) = -1 Then Return -1
		EndSelect
		If Sleep_checked(200) = -1 Then Return -1
		Write_log($massage)
	EndIf
EndFunc   ;==>Go_to_area

#cs
	Return 1 if pixel at ($x,$y) is exactly has $color color
#ce
Func Compare_pixel($x, $y, $color)
	Refresh_game_window()
	If GetPixel($x, $y) <> $color Then
		Return 0
	Else
		Return 1
	EndIf
EndFunc   ;==>Compare_pixel

#cs
	Loop Compare_pixel
#ce
Func Compare_pixels($pixels)
    For $i = 0 To UBound($pixels) - 1
        $x = $pixels[$i][0]
        $y = $pixels[$i][1]
        $color = $pixels[$i][2]
        If GetPixel($x, $y) <> $color Then
            Return 0
        EndIf
    Next
    Return 1
EndFunc   ;==>Compare_pixels

#cs
	wait for $color show at ($x, $y). When $time_out pass it will show error
	with $massage text
#ce
Func Wait_pixel($x, $y, $color, $time_out, $massage)
	$timer = TimerInit()
	While Compare_pixel($x, $y, $color) == 0 And (TimerDiff($timer) < $time_out)
		If Is_stop_requested() Then Return -1
		Sleep(100)
	WEnd
	If TimerDiff($timer) >= $time_out Then
		Write_log("Timeout " & $massage)
		Return -1
	EndIf
	Return 0
EndFunc   ;==>Wait_pixel

#cs
	Add exclude zone that not will considere by search function for specific
	$area. There is foour area correspond from Gate, duel, shop, card studio area
	respectively. Every $area has uniqe exclude zone.
#ce
Func Duel_world_exclude_area($area)
	AddExcludedArea(0, 0, 372, 749) ;left pane
	AddExcludedArea(913, 0, 1286, 749) ;right pane
	AddExcludedArea(372, 0, 914, 405) ;top pane
	AddExcludedArea(372, 653, 914, 749) ;bottom pane
	AddExcludedArea(525, 626, 752, 689);Event fragment
	AddExcludedArea(764, 480, 914, 653) ;character pane
	Switch $area
		Case 0
			AddExcludedArea(371, 357, 565, 506) ;duel school
		Case 1
			AddExcludedArea(369, 389, 506, 684) ;left
			AddExcludedArea(708, 394, 914, 665) ;right
		Case 2
			AddExcludedArea(716, 549, 669, 648) ;card trader
			AddExcludedArea(371, 358, 469, 687) ;left
			AddExcludedArea(445, 521, 501, 687) ;bottom left flower
			Switch $world
				Case 1
					AddExcludedArea(460, 426,570, 461);river maybe
			EndSwitch
		Case 3
			Switch $world
				Case 0
					AddExcludedArea(370, 420, 480, 647) ;right
				Case 1
					AddExcludedArea(370, 420, 581, 658) ;right
			EndSwitch
			AddExcludedArea(757, 428, 912, 648) ;left
	EndSwitch
EndFunc   ;==>Duel_world_exclude_area

#cs
	Return timer variabel in milisecond into second unit
#ce
Func time_s($time)
	Return Round($time / 1000, 1)
EndFunc   ;==>time_s

#cs
	Check if point ($x,$y) in $area is excluded from search zone.
#ce
Func Dbg_excluded($x, $y, $area, $in_world)
	$world = $in_world
	Duel_world_exclude_area($area)
	If IsExcluded($x, $y) Then
		MsgBox(0, "", "Excluded")
	Else
		MsgBox(0, "", "Clear")
	EndIf
EndFunc   ;==>Dbg_excluded

#cs
	Helper function for Dbg_excluded($x,$y,$area)
#ce
Func IsExcluded($x, $y)
	Refresh_game_window()
	If $UseAdbBackend Then Return AdbIsExcluded($x, $y)
	Return FFIsExcluded($x, $y, $GameHwnd)
EndFunc   ;==>IsExcluded

#cs
	Show pixel color of coordinate ($x,$y)
#ce
Func Dbg_print_color($x, $y)
	MsgBox($MB_SYSTEMMODAL, "Color", Hex(GetPixel($x, $y))) ;
	Move($x, $y)
	Exit
EndFunc   ;==>Dbg_print_color

#cs
	Show mean color of areas inside rectangle that defined by two coordinate
	($x1, $y1) and  ($x2, $y2)
#ce
Func Dbg_print_mean($x1, $y1, $x2, $y2)
	GUICreate("Mean", 200, 20)
	$display = GUICtrlCreateLabel("", 0, 0, 100, 20)
	GUISetState()

	While 1
		$msg = GUIGetMsg()
		Select
			Case $msg = $GUI_EVENT_CLOSE
				ExitLoop
			Case Else
				SnapShot($x1, $y1, $x2, $y2)
				$mean = FFComputeMeanValues()
				GUICtrlSetData($display, "Red" & $mean[0] & " G" & $mean[1] & " B" & $mean[2])
		 EndSelect
	WEnd
EndFunc   ;==>Dbg_print_mean

#cs
	Debug mode for search() function
#ce
Func Dbg_search($world_in, $area, $object)
	$world = $world_in
	If Go_to_area($area) == -1 Then
		MsgBox(0, "Error", "Area can't be decided")
		Exit
	EndIf
	Duel_world_exclude_area($area)

	Local $found
	Local $hObject = Object_color($object)
	FFAddColor($hObject[1])
	Local $pos = FFBestSpot(10, 7, 16, 632, 488, -1, 2)

	If Not @error Then
		MsgBox(0, "", $hObject[0] & " at " & $pos[0] & ", " & $pos[1] & " " & $pos[2] & " pixel detected.")
		ClickOn($pos[0], $pos[1], 2)
	Else
		MsgBox(0, "", "Not found")
	EndIf
	FFResetColors()
	FFResetExcludedAreas()
	Exit
EndFunc   ;==>Dbg_search

Func duel_over()
   Return Compare_pixel(420, 725, 0xFFFFFF) == 1 AND Compare_pixel(800, 150, 0x001E52) == 1
EndFunc

Func has_duel_screen()
   Return Compare_pixel(700, 700, 0x000000) == 1 AND Compare_pixel(700, 750, 0x000000) == 1
EndFunc

Func has_white_dialog()
   Return Compare_pixel(700, 700, 0xFFFFFF) == 1 AND Compare_pixel(700, 750, 0xFFFFFF) == 1
EndFunc


