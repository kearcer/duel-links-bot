#include <String.au3>
#include <MsgBoxConstants.au3>
#include <StringConstants.au3>
#include <GuiScrollBars.au3>
#include <GUIConstantsEx.au3>
#include <ButtonConstants.au3>
#include <GuiEdit.au3>
#include <FileConstants.au3>
#include <WinAPIFiles.au3>
#include "dlpc.au3"

Global $nMsg = ""
Global $duel_mode = 0
Global $coin = 1000
Global $OnTop = True
Global $Language = "zh"
Global $lHelp = 0
Global $LogFile = @ScriptDir & "\duel-links-bot.log"

;---------------------------- Start GUI --------------------------
gui()

;-------------------------- DEBUG commands -------------------------
;Move(650, 550)
;Dbg_print_color(400, 520)
;Dbg_print_color(650, 480)
;Dbg_print_color(650, 550)
;Move(498, 646)
;Dbg_search(0,0,16)
;Street_duel(0,0)
;Dbg_print_color(759,439)
;Dbg_excluded(504, 522,0)
;Gate_duel(10)
;-------------------------------------------------------------------
Func gui()
	Local $window_status = 0
	Global $hGui = GUICreate("Duel Links Bot Console",720, 520, 10, 20)

	Global $lTitle = GUICtrlCreateLabel("Duel Links Bot", 16, 12, 180, 24)
	GUICtrlSetFont($lTitle, 12, 800)
	Global $lSubtitle = GUICtrlCreateLabel("Run control, event tasks, and logs", 16, 35, 260, 18)
	Global $cLanguage = GUICtrlCreateCombo("中文", 590, 18, 110, 24)
	GUICtrlSetData($cLanguage, "English", "中文")

	Global $mainTab = GUICtrlCreateTab(12, 62, 696, 430)
		Global $tabBot = GUICtrlCreateTabItem("Bot")
			Global $log  = GUICtrlCreateEdit("",24, 98, 342, 330)
				write_log(Tr("readyLog"))

			Local $x = 382
			Local $y= 104
			Global $grpStatus = GUICtrlCreateGroup("Status", $x, 92, 302, 58)
			Global $l_status = GUICtrlCreateLabel("Duel Links: Stopped", $x + 14, 118, 180, 18)
			Global $lHotkeyHint = GUICtrlCreateLabel("F11 Start   F12 Stop", $x + 170, 118, 120, 18)

			Global $grpDuel = GUICtrlCreateGroup("Duel Mode",$x, 160,302,145)

			   GUIStartGroup()
			   Global $duel_enable = GUICtrlCreateCheckbox("Enable",$x + 14,$y + 80)
			   GUICtrlSetState($duel_enable, $GUI_CHECKED )
			   Global $rad_world0 = GUICtrlCreateRadio("Yu-Gi-Oh", $x + 14,$y + 104)
			   GUICtrlSetState($rad_world0, $GUI_CHECKED )
			   Global $rad_world1 = GUICtrlCreateRadio("GX", 	 $x+104, $y + 104)
			   Global $rad_world2 = GUICtrlCreateRadio("5DS", 	 $x + 194,    $y + 104)
			   Global $rad_world3 = GUICtrlCreateRadio("Zexal",  $x + 14, $y + 126)
			   Global $rad_world4 = GUICtrlCreateRadio("ARCV",   $x + 104,    $y + 126)
			   Global $rad_world5 = GUICtrlCreateRadio("Vrains", $x + 194, $y + 126)
			   Global $rad_world6 = GUICtrlCreateRadio("OLDN",   $x + 14,    $y + 148)
			   Global $rad_world7 = GUICtrlCreateRadio("Seven",  $x + 104, $y + 148)

			   GUIStartGroup()
			   Global $rad_sd = GUICtrlCreateRadio("Street duel", $x + 104, $y + 80)
			   GUICtrlSetState($rad_sd, $GUI_CHECKED )
			   Global $rad_gd = GUICtrlCreateRadio("Gate duel", $x+204, $y+80)

			Global $grpEvents = GUICtrlCreateGroup("Event Tasks",$x, 318,302,84)
			   GUIStartGroup()
			   Global $event_enable = GUICtrlCreateCheckbox("Battle City",$x + 14,$y+236)
			   Global $rad_dt = GUICtrlCreateRadio("Devine trial", $x + 114, $y+236)
			   GUICtrlSetState($rad_dt, $GUI_DISABLE)
			   Global $rad_lo = GUICtrlCreateRadio("Card Lottery", $x + 206, $y+236)
			   GUICtrlSetState($rad_lo, $GUI_DISABLE)
			   Global $rad_td = GUICtrlCreateRadio("Tag Duel", $x + 14, $y+260)
			   GUICtrlSetState($rad_td, $GUI_ENABLE)

			Global $grpInput = GUICtrlCreateGroup("Input Control", $x, 412, 302, 54)
			Global $lInputHint = GUICtrlCreateLabel("This bot moves and clicks your mouse while running.", $x + 14, 436, 270, 18)

			Global $but_duel = GUICtrlCreateButton("Start Duel", 24, 438, 160, 34)
			Global $but_stop = GUICtrlCreateButton("Stop", 196, 438, 80, 34)

		Global $tabHotkey = GUICtrlCreateTabItem("Hotkey")
			Global $lHotkey1 = GUICtrlCreateLabel("F9  : Pause/resume",24,100,240,20)
			Global $lHotkey2 = GUICtrlCreateLabel("F10: Terminate",24,125,240,20)
			Global $lHotkey3 = GUICtrlCreateLabel("F11: Start",24,150,240,20)
			Global $lHotkey4 = GUICtrlCreateLabel("F12: Quick stop",24,175,240,20)

		Global $tabSetting = GUICtrlCreateTabItem("Setting")
			$x = 24
			$y = 100
			Global $grpGeneral = GUICtrlCreateGroup("General",$x, $y,240,55)
				GUIStartGroup()
				Global $cOnTop = GUICtrlCreateCheckbox("Always on top", $x+14,124)
				GUICtrlSetState($cOnTop, $GUI_CHECKED)

			Global $grpStreetSetting = GUICtrlCreateGroup("Street Duel",$x, $y+70 ,360,60)
				GUIStartGroup()
				Global $cLoop = GUICtrlCreateCheckbox("Loop area", $x+14,194)
				Global $cOrb  = GUICtrlCreateCheckbox("Auto use orb", $x+114,194)
				Global $cGem  = GUICtrlCreateCheckbox("Check for gems", $x+230,194)
				GUICtrlSetState($cLoop, $GUI_CHECKED)
				GUICtrlSetState($cGem, $GUI_CHECKED)

			Global $grpGateSetting = GUICtrlCreateGroup("Gate Duel",$x, $y+145,240,55)
				GUIStartGroup()

			Global $tabHelp = GUICtrlCreateTabItem("Help")
				Global $lHelp = GUICtrlCreateLabel("",24,100,650,330,0x0000)
	GUICtrlCreateTabItem("")
	Apply_language()
	Initialize_game_window()

		HotKeySet("{F9}", "Hot_key")
	HotKeySet("{F10}", "Hot_key")
	HotKeySet("{F11}", "Hot_key")
	HotKeySet("{F12}", "Hot_key")

	GUISetState(@SW_SHOW)
	While 1
		If Control_gui(GUIGetMsg()) == -1 Then
			ExitLoop
		EndIf

		If $OnTop Then
			WinSetOnTop($hGui,'',  $WINDOWS_ONTOP)
		Else
			WinSetOnTop($hGui,'',  $WINDOWS_NOONTOP)
		EndIf

		If WinExists($title) Then
			If $window_status == 0 Then
				Set_status(True)
				$window_status = 1
			EndIf
		Else
			If $window_status == 1 Then
				Set_status(False)
				$window_status = 0
			EndIf
		EndIf
	WEnd
	GUIDelete($hGui)
	Exit
EndFunc

Func write_log($variable)
	Local $line = @YEAR & "-" & @MON & "-" & @MDAY & " " & @HOUR & ":" & @MIN & ":" & @SEC & " " & $variable
	_GUICtrlEdit_AppendText($log, $line & @CRLF)
	FileWrite($LogFile, $line & @CRLF)
EndFunc

Func duel_bot()
	$StopRequested = False
	$Loop = _IsChecked($cLoop)
	If Not Initialize_game_window() Then Return
	Switch $duel_mode
		 Case 0
			Street_duel($world, get_area(1))
		 Case 1
			Gate_duel(1176/24)
		 Case 2
			#comments-start divine_trial()
			#comments-end
			Battle_city()
		 Case 3
			card_lottery($coin)
		 Case 4
			Tag_duel()
	EndSwitch
EndFunc

Func Create_log()
	$log  = GUICtrlCreateEdit("",10, 10, 200, 330)
EndFunc

Func Clear_log()
	GUICtrlDelete($log)
	Create_log()
EndFunc

Func Tr($key)
	Switch $key
		Case "title"
			If $Language == "zh" Then Return "Duel Links 自动助手"
			Return "Duel Links Bot Console"
		Case "subtitle"
			If $Language == "zh" Then Return "运行控制、活动任务与日志监控"
			Return "Run control, event tasks, and logs"
		Case "bot"
			If $Language == "zh" Then Return "控制�?
			Return "Bot"
		Case "hotkey"
			If $Language == "zh" Then Return "快捷�?
			Return "Hotkey"
		Case "setting"
			If $Language == "zh" Then Return "设置"
			Return "Setting"
		Case "help"
			If $Language == "zh" Then Return "帮助"
			Return "Help"
		Case "status"
			If $Language == "zh" Then Return "状�?
			Return "Status"
		Case "running"
			If $Language == "zh" Then Return "游戏状态：运行�?
			Return "Duel Links: Running"
		Case "stopped"
			If $Language == "zh" Then Return "游戏状态：已停�?
			Return "Duel Links: Stopped"
		Case "hotkeyHint"
			If $Language == "zh" Then Return "F11 启动   F12 停止"
			Return "F11 Start   F12 Stop"
		Case "duelMode"
			If $Language == "zh" Then Return "决斗模式"
			Return "Duel Mode"
		Case "enable"
			If $Language == "zh" Then Return "启用"
			Return "Enable"
		Case "streetDuel"
			If $Language == "zh" Then Return "街头决斗"
			Return "Street duel"
		Case "gateDuel"
			If $Language == "zh" Then Return "传送门决斗"
			Return "Gate duel"
		Case "events"
			If $Language == "zh" Then Return "活动任务"
			Return "Event Tasks"
		Case "battleCity"
			If $Language == "zh" Then Return "战斗城市"
			Return "Battle City"
		Case "devineTrial"
			If $Language == "zh" Then Return "神之试炼"
			Return "Devine trial"
		Case "cardLottery"
			If $Language == "zh" Then Return "卡片抽奖"
			Return "Card Lottery"
		Case "tagDuel"
			If $Language == "zh" Then Return "组队决斗"
			Return "Tag Duel"
		Case "inputControl"
			If $Language == "zh" Then Return "输入控制"
			Return "Input Control"
		Case "inputHint"
			If $Language == "zh" Then Return "运行时会移动并点击鼠标来操作游戏窗口�?
			Return "This bot moves and clicks your mouse while running."
		Case "readyLog"
			If $Language == "zh" Then Return "就绪。请确认已经登录游戏�?
			Return "Ready. Make sure you are already logged in."
		Case "start"
			If $Language == "zh" Then Return "开始决�?
			Return "Start Duel"
		Case "stop"
			If $Language == "zh" Then Return "停止"
			Return "Stop"
		Case "pauseResume"
			If $Language == "zh" Then Return "F9  : 暂停/继续"
			Return "F9  : Pause/resume"
		Case "terminate"
			If $Language == "zh" Then Return "F10: 终止"
			Return "F10: Terminate"
		Case "startHotkey"
			If $Language == "zh" Then Return "F11: 启动"
			Return "F11: Start"
		Case "stopHotkey"
			If $Language == "zh" Then Return "F12: 快速停�?
			Return "F12: Quick stop"
		Case "general"
			If $Language == "zh" Then Return "通用"
			Return "General"
		Case "alwaysOnTop"
			If $Language == "zh" Then Return "窗口置顶"
			Return "Always on top"
		Case "streetSetting"
			If $Language == "zh" Then Return "街头决斗"
			Return "Street Duel"
		Case "loopArea"
			If $Language == "zh" Then Return "循环区域"
			Return "Loop area"
		Case "autoOrb"
			If $Language == "zh" Then Return "自动使用珠子"
			Return "Auto use orb"
		Case "checkGems"
			If $Language == "zh" Then Return "检查宝�?
			Return "Check for gems"
		Case "gateSetting"
			If $Language == "zh" Then Return "传送门决斗"
			Return "Gate Duel"
		Case "helpText"
			If $Language == "zh" Then Return "https://github.com/ftuyama/duel-links-bot" & @CRLF & @CRLF & _
				"- 所有自动化功能默认从街头区域开始使用�? & @CRLF & _
				"- 如果机器人卡住，�?F10 终止。需要暂停时�?F9，再按一次继续�? & @CRLF & @CRLF & _
				"街头决斗" & @CRLF & _
				"- 循环区域：到达工作室区域后会返回传送门区域继续�? & @CRLF & @CRLF & _
				"请设置正确分辨率以保证识别和点击准确�? & @CRLF & _
				"Windows�?366x768，缩�?100%" & @CRLF & _
				"Duel Links�?280x720（Alt + Enter 切换窗口模式�?
			Return "https://github.com/ftuyama/duel-links-bot" & @CRLF & @CRLF & _
				"- All bot functions assume you are in the street area." & @CRLF & _
				"- If the bot gets stuck, press F10 to terminate it. Press F9 to pause and press it again to continue." & @CRLF & @CRLF & _
				"Street Duel" & @CRLF & _
				"- Loop area: the bot returns to the Gate Area after the Studio Area." & @CRLF & @CRLF & _
				"Set the correct resolution to make it work:" & @CRLF & _
				"Windows:    1366x768, scale 100%" & @CRLF & _
				"Duel Links: 1280x720 (Alt + Enter toggles window mode)"
	EndSwitch
	Return $key
EndFunc

Func Set_status($isRunning)
	If $isRunning Then
		GUICtrlSetData($l_status, Tr("running"))
	Else
		GUICtrlSetData($l_status, Tr("stopped"))
	EndIf
EndFunc

Func Apply_language()
	GUICtrlSetData($lTitle, Tr("title"))
	GUICtrlSetData($lSubtitle, Tr("subtitle"))
	If $Language == "zh" Then
		GUICtrlSetData($cLanguage, "中文")
	Else
		GUICtrlSetData($cLanguage, "English")
	EndIf

	GUICtrlSetData($tabBot, Tr("bot"))
	GUICtrlSetData($tabHotkey, Tr("hotkey"))
	GUICtrlSetData($tabSetting, Tr("setting"))
	GUICtrlSetData($tabHelp, Tr("help"))
	GUICtrlSetData($grpStatus, Tr("status"))
	GUICtrlSetData($lHotkeyHint, Tr("hotkeyHint"))
	GUICtrlSetData($grpDuel, Tr("duelMode"))
	GUICtrlSetData($duel_enable, Tr("enable"))
	GUICtrlSetData($rad_sd, Tr("streetDuel"))
	GUICtrlSetData($rad_gd, Tr("gateDuel"))
	GUICtrlSetData($grpEvents, Tr("events"))
	GUICtrlSetData($event_enable, Tr("battleCity"))
	GUICtrlSetData($rad_dt, Tr("devineTrial"))
	GUICtrlSetData($rad_lo, Tr("cardLottery"))
	GUICtrlSetData($rad_td, Tr("tagDuel"))
	GUICtrlSetData($grpInput, Tr("inputControl"))
	GUICtrlSetData($lInputHint, Tr("inputHint"))
	GUICtrlSetData($but_duel, Tr("start"))
	GUICtrlSetData($but_stop, Tr("stop"))
	GUICtrlSetData($lHotkey1, Tr("pauseResume"))
	GUICtrlSetData($lHotkey2, Tr("terminate"))
	GUICtrlSetData($lHotkey3, Tr("startHotkey"))
	GUICtrlSetData($lHotkey4, Tr("stopHotkey"))
	GUICtrlSetData($grpGeneral, Tr("general"))
	GUICtrlSetData($cOnTop, Tr("alwaysOnTop"))
	GUICtrlSetData($grpStreetSetting, Tr("streetSetting"))
	GUICtrlSetData($cLoop, Tr("loopArea"))
	GUICtrlSetData($cOrb, Tr("autoOrb"))
	GUICtrlSetData($cGem, Tr("checkGems"))
	GUICtrlSetData($grpGateSetting, Tr("gateSetting"))
	GUICtrlSetData($lHelp, Tr("helpText"))
	Set_status(WinExists($title))
EndFunc

Func Hot_key()
	Switch @HotKeyPressed
		Case "{F9}"
			$sPaused = Not $sPaused
			Local $Informed = False
			While $sPaused
				Control_gui(GUIGetMsg())
				If $StopRequested Then ExitLoop
				$timer = TimerInit()
				If Not $Informed Then
					Write_log("Bot Paused.")
					$Informed = True
				EndIf
				Sleep(100)
			WEnd
			If Not $sPaused  And $Informed Then
				Write_log("Bot resume.")
			EndIf
		Case "{F10}"
			Write_log("Bot terminated.")
			Request_stop()
		Case "{F11}"
			Write_log("Bot started by hotkey.")
			duel_bot()
		Case "{F12}"
			Write_log("Bot quick stopped.")
			Request_stop()
	EndSwitch
EndFunc

Func Control_gui($nMsg)
		Switch $nMsg
			Case $GUI_EVENT_CLOSE
				Return -1
			Case $cLanguage
				If GUICtrlRead($cLanguage) == "English" Then
					$Language = "en"
				Else
					$Language = "zh"
				EndIf
				Apply_language()
			Case $duel_enable
			   if GUICtrlRead($duel_enable) == $GUI_UNCHECKED Then
				  disable_duel_menu()
			   Else
				  GUICtrlSetState($rad_sd, $GUI_ENABLE)
				  GUICtrlSetState($rad_gd, $GUI_ENABLE)
				  GUICtrlSetState($rad_world0, $GUI_ENABLE)
				  GUICtrlSetState($rad_world1, $GUI_ENABLE)

				  disalbe_bcd_menu()
			   EndIf
			Case $event_enable
			   If GUICtrlRead($event_enable) == $GUI_UNCHECKED Then
				  disalbe_bcd_menu()
			   Else
				  disable_duel_menu()
				  GUICtrlSetState($rad_dt, $GUI_ENABLE)
				  GUICtrlSetState($rad_lo, $GUI_ENABLE)
			   EndIf
			Case $but_duel
			   duel_bot()
			Case $but_stop
			   Write_log("Bot stopped from UI.")
			   Request_stop()
			Case $rad_sd
			   $duel_mode = 0
			Case $rad_gd
			   $duel_mode = 1
			Case $rad_dt
			   $duel_mode = 2
			Case $rad_lo
			   $duel_mode = 3
			Case $rad_td
			   $duel_mode = 4
			Case $rad_world0
				$world = 0
			Case $rad_world1
				$world = 1
			Case $rad_world2
				$world = 2
			Case $rad_world3
				$world = 3
			Case $rad_world4
				$world = 4
			Case $rad_world5
				$world = 5
			Case $rad_world6
				$world = 6
			Case $rad_world7
				$world = 7
			Case $cLoop
				if _IsChecked($cLoop) Then
					$Loop = True
				Else
					$Loop = false
				EndIf
			Case $cGem
				if _IsChecked($cGem) Then
					$CheckGems = True
				Else
					$CheckGems = false
				EndIf
			 Case $cOrb
				if _IsChecked($cOrb) Then
					$auto_orb_reload = True
				Else
					$auto_orb_reload = false
				EndIf
			Case $cOnTop
				if _IsChecked($cOnTop) Then
					$OnTop = True
				Else
					$OnTop = false
				EndIf
		EndSwitch
EndFunc

Func disable_duel_menu()
   GUICtrlSetState($duel_enable, $GUI_UNCHECKED)

   GUICtrlSetState($rad_sd, $GUI_UNCHECKED)
   GUICtrlSetState($rad_sd, $GUI_DISABLE)

   GUICtrlSetState($rad_gd, $GUI_UNCHECKED)
   GUICtrlSetState($rad_gd, $GUI_DISABLE)

   GUICtrlSetState($rad_world0, $GUI_UNCHECKED)
   GUICtrlSetState($rad_world0, $GUI_DISABLE)

   GUICtrlSetState($rad_world1, $GUI_UNCHECKED)
   GUICtrlSetState($rad_world1, $GUI_DISABLE)
EndFunc

Func disalbe_bcd_menu()
   GUICtrlSetState($event_enable, $GUI_UNCHECKED)

   GUICtrlSetState($rad_dt, $GUI_UNCHECKED)
   GUICtrlSetState($rad_dt, $GUI_DISABLE)

   GUICtrlSetState($rad_lo, $GUI_UNCHECKED)
   GUICtrlSetState($rad_lo, $GUI_DISABLE)
EndFunc

Func _IsChecked($idControlID)
    Return BitAND(GUICtrlRead($idControlID), $GUI_CHECKED) = $GUI_CHECKED
EndFunc