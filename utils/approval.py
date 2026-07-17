import discord
from config import ALLOWED_USER_ID
from utils.logger import logger

class ApprovalView(discord.ui.View):
    def __init__(self, command: str):
        # 60 seconds timeout
        super().__init__(timeout=60.0)
        self.command = command
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != ALLOWED_USER_ID:
            await interaction.response.send_message("Only the owner can approve commands.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✅")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        
        # Disable buttons
        for child in self.children:
            child.disabled = True
            
        await interaction.response.edit_message(content=f"✅ Command approved by {interaction.user.mention}. Executing...", view=self)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        
        # Disable buttons
        for child in self.children:
            child.disabled = True
            
        await interaction.response.edit_message(content=f"❌ Command rejected by {interaction.user.mention}.", view=self)

    async def on_timeout(self):
        self.value = False
        for child in self.children:
            child.disabled = True
            
        # Try to update the message to show it timed out, requires the message object
        # We can't edit it directly from here without the message object, so the caller should handle it if needed.
        # But we can just let it fail silently or log it.
        logger.info(f"Approval for command '{self.command}' timed out.")
