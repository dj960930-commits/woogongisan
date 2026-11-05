package com.woogong.app

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import android.app.Activity

private val Day = lightColorScheme(
 primary=Color(0xff765516),onPrimary=Color.White,primaryContainer=Color(0xfff4e7c9),onPrimaryContainer=Color(0xff50370c),
 background=Color(0xfff5f4f1),onBackground=Color(0xff191918),surface=Color(0xfffefdfb),onSurface=Color(0xff191918),
 surfaceVariant=Color(0xffedeae4),onSurfaceVariant=Color(0xff5e5b54),outline=Color(0xff817b70),outlineVariant=Color(0xffdedbd3),
 secondary=Color(0xff59574e),secondaryContainer=Color(0xffe9e5dd),onSecondaryContainer=Color(0xff322f29),
 tertiary=Color(0xff386966),tertiaryContainer=Color(0xffdceeea),onTertiaryContainer=Color(0xff1b4542),
 surfaceContainerLow=Color(0xfffaf8f4),surfaceContainer=Color(0xfff0ede7),surfaceContainerHigh=Color(0xffeae6df))
private val Night = darkColorScheme(
 primary=Color(0xffeac87a),onPrimary=Color(0xff29200e),primaryContainer=Color(0xff362c1b),onPrimaryContainer=Color(0xfff5db9f),
 background=Color(0xff101011),onBackground=Color(0xfff4f1eb),surface=Color(0xff1a1a1c),onSurface=Color(0xfff4f1eb),
 surfaceVariant=Color(0xff29282a),onSurfaceVariant=Color(0xffb6b1a8),outline=Color(0xff918a7f),outlineVariant=Color(0xff373537),
 secondary=Color(0xffc6bfb2),secondaryContainer=Color(0xff35322d),onSecondaryContainer=Color(0xffe8e0d3),
 tertiary=Color(0xffa3d3cc),tertiaryContainer=Color(0xff23423f),onTertiaryContainer=Color(0xffc2ebe6),
 surfaceContainerLow=Color(0xff171719),surfaceContainer=Color(0xff222224),surfaceContainerHigh=Color(0xff2a2a2c))

private val AppTypography = Typography(
 headlineSmall=TextStyle(fontSize=24.sp,lineHeight=30.sp,fontWeight=FontWeight.Bold,letterSpacing=(-.6).sp),
 titleMedium=TextStyle(fontSize=16.sp,lineHeight=22.sp,fontWeight=FontWeight.SemiBold),
 bodyLarge=TextStyle(fontSize=15.sp,lineHeight=21.sp),
 bodyMedium=TextStyle(fontSize=14.sp,lineHeight=20.sp),
 bodySmall=TextStyle(fontSize=12.sp,lineHeight=17.sp),
 labelLarge=TextStyle(fontSize=13.sp,lineHeight=18.sp,fontWeight=FontWeight.SemiBold)
)

@Composable internal fun WoogongTheme(content:@Composable ()->Unit){
 val dark=isSystemInDarkTheme();val view=LocalView.current
 SideEffect{
  (view.context as? Activity)?.let{activity->
   WindowCompat.getInsetsController(activity.window,view).apply{
    isAppearanceLightStatusBars=!dark;isAppearanceLightNavigationBars=!dark
   }
  }
 }
 MaterialTheme(colorScheme=if(dark)Night else Day, typography=AppTypography,
  shapes=Shapes(small=RoundedCornerShape(8.dp),medium=RoundedCornerShape(12.dp),
   large=RoundedCornerShape(18.dp),extraLarge=RoundedCornerShape(24.dp)),content=content)
}

internal val Ink:Color @Composable get()=MaterialTheme.colorScheme.onSurface
internal val Mint:Color @Composable get()=MaterialTheme.colorScheme.primary
internal val Gold:Color @Composable get()=if(isSystemInDarkTheme())Color(0xffe5bb70) else Color(0xff906824)
